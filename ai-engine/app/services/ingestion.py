"""Dataset ingestion: COCO and YOLO layouts unified into `Sample` records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.errors import AnalysisError
from app.core.logging import get_logger
from app.services.hashing import phash64, sha256_bytes

log = get_logger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
UNATTRIBUTED = "unattributed"


@dataclass
class Sample:
    idx: int
    rel_path: str
    abs_path: Path
    sha256: str
    phash: int
    label_id: int | None
    label_name: str
    contributor: str
    width: int
    height: int
    image: np.ndarray | None = None   # optional in-memory cache (RGB, resized)


@dataclass
class IngestResult:
    samples: list[Sample]
    corrupted: list[dict]
    missing_labels: int
    class_names: dict[int, str]
    contributors: list[str]
    format_used: str
    truncated: bool
    manifest_present: bool = True


# ---------------------------------------------------------------------------
# format detection
# ---------------------------------------------------------------------------


def detect_format(root: Path) -> str:
    """Best-effort detection of COCO vs YOLO layout."""
    # YOLO markers
    for marker in ("data.yaml", "data.yml", "classes.txt"):
        if (root / marker).exists():
            return "yolo"
    for path in root.rglob("*"):
        if path.is_dir() and path.name == "labels":
            return "yolo"
    # COCO markers: any json with "images" + "annotations"
    jsons = list(root.glob("*.json")) + (
        list((root / "annotations").glob("*.json")) if (root / "annotations").is_dir() else []
    )
    for jp in jsons[:20]:
        try:
            head = jp.read_text(encoding="utf-8", errors="ignore")[:4096]
            if '"images"' in head and '"annotations"' in head:
                return "coco"
        except OSError:
            continue
    raise AnalysisError(
        "could not detect dataset format under "
        f"{root}: no YOLO markers (labels/, data.yaml) or COCO annotation json found"
    )


# ---------------------------------------------------------------------------
# contributor manifests
# ---------------------------------------------------------------------------


def build_manifest(root: Path, override: dict[str, str] | None) -> dict[str, str]:
    """Contributor attribution: explicit override > contributors.json > none."""
    if override:
        return {_norm(k): str(v) for k, v in override.items()}
    manifest_file = root / "contributors.json"
    if not manifest_file.exists():
        return {}
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("contributors.json unreadable: %s", exc)
        return {}
    out: dict[str, str] = {}
    if isinstance(data, dict):
        out = {_norm(str(k)): str(v) for k, v in data.items()}
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            contributor = str(item.get("contributor", UNATTRIBUTED))
            for rel in item.get("paths", []):
                out[_norm(str(rel))] = contributor
    return out


def _norm(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def _contributor_for(manifest: dict[str, str], rel: str, name: str) -> str:
    return manifest.get(_norm(rel)) or manifest.get(_norm(name)) or UNATTRIBUTED


# ---------------------------------------------------------------------------
# decoding
# ---------------------------------------------------------------------------


def _decode(path: Path, image_size: int) -> tuple[np.ndarray, np.ndarray, int, int, str] | None:
    """Read one image → (rgb_resized, gray_full, width, height, sha256). None if corrupt."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        log.warning("unreadable image %s: %s", path, exc)
        return None
    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    height, width = arr.shape[:2]
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_AREA)
    return resized, gray, int(width), int(height), sha256_bytes(data)


def _walk_images(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


# ---------------------------------------------------------------------------
# COCO loader
# ---------------------------------------------------------------------------


def _find_coco_annotation(root: Path) -> Path:
    candidates = list(root.glob("*.json")) + (
        list((root / "annotations").glob("*.json")) if (root / "annotations").is_dir() else []
    )
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "images" in data and "annotations" in data:
            return candidate
    raise AnalysisError(f"no COCO annotation file (images+annotations) found under {root}")


def load_coco(
    root: Path,
    manifest: dict[str, str],
    image_size: int,
    cache_images_max: int,
    max_samples: int,
) -> IngestResult:
    ann_path = _find_coco_annotation(root)
    data = json.loads(ann_path.read_text(encoding="utf-8"))

    class_names = {
        int(cat["id"]): str(cat.get("name", f"class_{cat['id']}"))
        for cat in data.get("categories", [])
    }
    image_meta = {int(img["id"]): str(img.get("file_name", "")) for img in data.get("images", [])}

    first_label: dict[int, int] = {}
    for ann in sorted(data.get("annotations", []), key=lambda a: int(a.get("id", 0))):
        image_id = int(ann["image_id"])
        if image_id not in first_label:
            first_label[image_id] = int(ann.get("category_id", -1))

    # file resolution: direct path first, then basename index over the tree
    by_name: dict[str, Path] = {}
    for path in _walk_images(root):
        by_name.setdefault(path.name, path)

    samples: list[Sample] = []
    corrupted: list[dict] = []
    truncated = False
    idx = 0
    for image_id, file_name in sorted(image_meta.items()):
        if len(samples) >= max_samples:
            truncated = True
            break
        direct = root / file_name
        path = direct if direct.exists() else by_name.get(Path(file_name).name)
        if path is None or not path.exists():
            corrupted.append({"rel_path": file_name, "reason": "file not found"})
            continue
        decoded = _decode(path, image_size)
        if decoded is None:
            corrupted.append({"rel_path": _norm(str(path.relative_to(root))), "reason": "decode failed"})
            continue
        resized, gray, width, height, sha = decoded
        label_id = first_label.get(image_id)
        rel = _norm(str(path.relative_to(root)))
        samples.append(
            Sample(
                idx=idx,
                rel_path=rel,
                abs_path=path,
                sha256=sha,
                phash=phash64(gray),
                label_id=label_id,
                label_name=class_names.get(label_id, "__unlabeled__")
                if label_id is not None
                else "__unlabeled__",
                contributor=_contributor_for(manifest, rel, path.name),
                width=width,
                height=height,
                image=resized if len(samples) < cache_images_max else None,
            )
        )
        idx += 1

    return _finish(samples, corrupted, class_names, "coco", truncated, bool(manifest))


# ---------------------------------------------------------------------------
# YOLO loader
# ---------------------------------------------------------------------------


def _parse_data_yaml_names(path: Path) -> dict[int, str]:
    """Minimal parser for the `names:` block of a YOLO data.yaml (no PyYAML)."""
    names: dict[int, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return names
    in_names = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("names:"):
            rest = stripped[len("names:"):].strip()
            if rest.startswith("[") and rest.endswith("]"):
                for i, item in enumerate(rest[1:-1].split(",")):
                    name = item.strip().strip("'\"")
                    if name:
                        names[i] = name
                return names
            in_names = True
            continue
        if in_names:
            if not stripped or stripped.startswith(("#", "nc:", "train:", "val:", "test:")):
                if stripped and not stripped.startswith("#") and ":" not in stripped:
                    in_names = False
                    continue
                if stripped.startswith(("- ",)):
                    idx = len(names)
                    names[idx] = stripped[2:].strip().strip("'\"")
                    continue
                if ":" in stripped and not stripped.startswith("-"):
                    key, _, value = stripped.partition(":")
                    if key.strip().isdigit():
                        names[int(key.strip())] = value.strip().strip("'\"")
                        continue
                    in_names = False
    return names


def _parse_classes_txt(path: Path) -> dict[int, str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {}
    return {i: line.strip() for i, line in enumerate(lines) if line.strip()}


def _yolo_label_path(image_path: Path, root: Path, label_index: dict[str, Path]) -> Path | None:
    parts = list(image_path.relative_to(root).parts)
    if "images" in parts:
        parts[parts.index("images")] = "labels"
        candidate = root.joinpath(*parts).with_suffix(".txt")
        if candidate.exists():
            return candidate
    return label_index.get(image_path.stem)


def load_yolo(
    root: Path,
    manifest: dict[str, str],
    image_size: int,
    cache_images_max: int,
    max_samples: int,
) -> IngestResult:
    label_files = sorted(root.rglob("*.txt"))
    label_index = {p.stem: p for p in label_files if p.name != "classes.txt"}

    class_names: dict[int, str] = {}
    for marker in (root / "data.yaml", root / "data.yml"):
        if marker.exists():
            class_names = _parse_data_yaml_names(marker)
            break
    if not class_names:
        classes_txt = next((p for p in root.rglob("classes.txt")), None)
        if classes_txt:
            class_names = _parse_classes_txt(classes_txt)

    samples: list[Sample] = []
    corrupted: list[dict] = []
    truncated = False
    idx = 0
    for path in _walk_images(root):
        if len(samples) >= max_samples:
            truncated = True
            break
        decoded = _decode(path, image_size)
        if decoded is None:
            corrupted.append({"rel_path": _norm(str(path.relative_to(root))), "reason": "decode failed"})
            continue
        resized, gray, width, height, sha = decoded
        rel = _norm(str(path.relative_to(root)))
        label_path = _yolo_label_path(path, root, label_index)
        label_id: int | None = None
        if label_path is not None:
            first = label_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            first = [ln for ln in first if ln.strip()]
            if first:
                try:
                    label_id = int(float(first[0].split()[0]))
                except (ValueError, IndexError):
                    label_id = None
        samples.append(
            Sample(
                idx=idx,
                rel_path=rel,
                abs_path=path,
                sha256=sha,
                phash=phash64(gray),
                label_id=label_id,
                label_name=class_names.get(label_id, f"class_{label_id}")
                if label_id is not None
                else "__unlabeled__",
                contributor=_contributor_for(manifest, rel, path.name),
                width=width,
                height=height,
                image=resized if len(samples) < cache_images_max else None,
            )
        )
        idx += 1

    return _finish(samples, corrupted, class_names, "yolo", truncated, bool(manifest))


# ---------------------------------------------------------------------------
# shared finish
# ---------------------------------------------------------------------------


def _finish(
    samples: list[Sample],
    corrupted: list[dict],
    class_names: dict[int, str],
    fmt: str,
    truncated: bool,
    manifest_present: bool,
) -> IngestResult:
    contributors = sorted({s.contributor for s in samples})
    missing = sum(1 for s in samples if s.label_id is None)
    return IngestResult(
        samples=samples,
        corrupted=corrupted,
        missing_labels=missing,
        class_names=class_names,
        contributors=contributors,
        format_used=fmt,
        truncated=truncated,
        manifest_present=manifest_present,
    )


def ingest_dataset(
    root: Path,
    dataset_format: str,
    manifest_override: dict[str, str] | None,
    image_size: int,
    cache_images_max: int,
    max_samples: int,
) -> IngestResult:
    if not root.is_dir():
        raise AnalysisError(f"dataset source is not a directory: {root}")
    fmt = detect_format(root) if dataset_format == "AUTO" else dataset_format.lower()
    if fmt not in ("coco", "yolo"):
        raise AnalysisError(f"unsupported dataset format: {fmt}")
    manifest = build_manifest(root, manifest_override)
    loader = load_coco if fmt == "coco" else load_yolo
    result = loader(root, manifest, image_size, cache_images_max, max_samples)
    log.info(
        "ingested %d samples (%d corrupted, %d missing labels, format=%s)",
        len(result.samples), len(result.corrupted), result.missing_labels, fmt,
    )
    return result
