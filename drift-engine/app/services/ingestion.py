"""Dataset-side ingestion: image walk, decode, EXIF, labels (COCO/YOLO), zip."""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.errors import AnalysisError
from app.core.logging import get_logger

log = get_logger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


@dataclass
class SideSample:
    rel_path: str
    abs_path: Path
    label_id: int | None
    phash: int


@dataclass
class SideData:
    path: Path
    samples: list[SideSample] = field(default_factory=list)
    class_names: dict[int, str] = field(default_factory=dict)
    exif: dict[str, dict[str, object]] = field(default_factory=dict)  # rel_path -> tags
    format_used: str = "unknown"


def extract_zip_if_needed(path: Path) -> Path:
    """Safely extract a .zip to the workspace and return the extract root."""
    if not path.exists():
        raise AnalysisError(f"path does not exist: {path}")
    if path.is_dir() or path.suffix.lower() != ".zip":
        return path
    settings = get_settings()
    dest = settings.workspace_dir / "extracts" / f"{path.stem}-{abs(hash(str(path))) % 10**8}"
    if dest.exists():
        return dest
    dest_resolved = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    with zipfile.ZipFile(path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise AnalysisError(f"unsafe archive entry: {member.filename}")
            total += member.file_size
            if total > 20 * 1024**3:
                raise AnalysisError("archive exceeds uncompressed size limit")
            count += 1
            if count > 200_000:
                raise AnalysisError("archive exceeds file count limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    return dest


def _walk_images(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def _read_exif(path: Path) -> dict[str, object]:
    """EXIF tags we care about, absent gracefully when missing."""
    tags: dict[str, object] = {}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        with Image.open(path) as img:
            exif = img._getexif()
        if not exif:
            return tags
        named = {TAGS.get(k, k): v for k, v in exif.items()}
        if named.get("Make"):
            tags["make"] = str(named["Make"]).strip()
        if named.get("Model"):
            tags["model"] = str(named["Model"]).strip()
        if named.get("DateTimeOriginal") or named.get("DateTime"):
            raw_time = str(named.get("DateTimeOriginal") or named.get("DateTime"))
            try:
                tags["month"] = int(raw_time[5:7])
            except (ValueError, IndexError):
                pass
        if named.get("Flash") is not None:
            try:
                tags["flash"] = int(named["Flash"]) & 1 == 1
            except (ValueError, TypeError):
                pass
    except Exception:
        return tags
    return tags


def _labels_for(root: Path, images: list[Path]) -> tuple[dict[str, int], dict[int, str], str]:
    """First-label-per-image lookup + class names. Returns (by_rel, names, fmt)."""
    by_rel: dict[str, int] = {}
    names: dict[int, str] = {}

    coco_jsons = list(root.glob("*.json")) + (
        list((root / "annotations").glob("*.json")) if (root / "annotations").is_dir() else []
    )
    for jp in coco_jsons[:20]:
        try:
            data = json.loads(jp.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError):
            continue
        if not (isinstance(data, dict) and "images" in data and "annotations" in data):
            continue
        names = {int(c["id"]): str(c.get("name", f"class_{c['id']}")) for c in data.get("categories", [])}
        first: dict[int, int] = {}
        for ann in sorted(data.get("annotations", []), key=lambda a: int(a.get("id", 0))):
            image_id = int(ann["image_id"])
            if image_id not in first:
                first[image_id] = int(ann.get("category_id", -1))
        for img in data.get("images", []):
            label = first.get(int(img["id"]))
            if label is not None:
                by_rel[str(img.get("file_name", "")).replace("\\", "/")] = label
        return by_rel, names, "coco"

    label_files = {p.stem: p for p in root.rglob("*.txt") if p.name != "classes.txt"}
    if label_files:
        yaml_names: dict[int, str] = {}
        for marker in (root / "data.yaml", root / "data.yml"):
            if marker.exists():
                yaml_names = _parse_yaml_names(marker)
                break
        if not yaml_names:
            classes_txt = next((p for p in root.rglob("classes.txt")), None)
            if classes_txt:
                yaml_names = {
                    i: line.strip()
                    for i, line in enumerate(classes_txt.read_text(encoding="utf-8", errors="ignore").splitlines())
                    if line.strip()
                }
        for image in images:
            lp = label_files.get(image.stem)
            if lp is None:
                continue
            lines = [ln for ln in lp.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
            if lines:
                try:
                    by_rel[image.name] = int(float(lines[0].split()[0]))
                except (ValueError, IndexError):
                    continue
        return by_rel, yaml_names, "yolo"

    return by_rel, names, "unlabelled"


def _parse_yaml_names(path: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    in_names = False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("names:"):
            rest = stripped[len("names:"):].strip()
            if rest.startswith("[") and rest.endswith("]"):
                for i, item in enumerate(rest[1:-1].split(",")):
                    if item.strip().strip("'\""):
                        names[i] = item.strip().strip("'\"")
                return names
            in_names = True
            continue
        if in_names:
            if stripped.startswith("- "):
                names[len(names)] = stripped[2:].strip().strip("'\"")
            elif ":" in stripped and stripped.split(":")[0].strip().isdigit():
                key, _, value = stripped.partition(":")
                names[int(key.strip())] = value.strip().strip("'\"")
            elif stripped and not stripped.startswith("#"):
                in_names = False
    return names


def load_side(path: Path, max_samples: int) -> SideData:
    """Load one dataset side: samples (path, label, pHash) + EXIF per image."""
    root = extract_zip_if_needed(path)
    if not root.is_dir():
        raise AnalysisError(f"source is not a directory after extraction: {root}")
    images = _walk_images(root)[:max_samples]
    if not images:
        raise AnalysisError(f"no decodable images found under {root}")

    labels, names, fmt = _labels_for(root, images)
    side = SideData(path=root, class_names=names, format_used=fmt)
    from app.services.features import phash64

    for image in images:
        data = image.read_bytes()
        arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            continue
        rel = str(image.relative_to(root)).replace("\\", "/")
        label = labels.get(rel, labels.get(image.name))
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        side.samples.append(
            SideSample(rel_path=rel, abs_path=image, label_id=label, phash=phash64(gray))
        )
        side.exif[rel] = _read_exif(image)

    log.info("side %s: %d images, format=%s, exif coverage=%.0f%%",
             root.name, len(side.samples), fmt,
             100 * sum(1 for t in side.exif.values() if t) / max(1, len(side.exif)))
    return side
