"""End-to-end tests: synthetic YOLO dataset with planted assurance issues.

The fixture plants every detector's target signal:
  * exact duplicates           (team-alpha copies)
  * near-duplicate flooding    (team-beta, 7 near-identical squares)
  * plain label flips          (team-alpha red circles labelled blue_square)
  * trigger injection          (team-beta red circles + white top-right patch)
  * OOD samples                (2 white images)
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

IMAGE_SIZE = 96
PATCH = 24  # trigger patch == one grid cell (96/4)


def _base_image(cls: int, seed: int) -> np.ndarray:
    """Class-distinguishable but individually distinct: strong per-pixel noise
    (decorrelates full-image pHash) and jittered geometry per image."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 110, (IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
    if cls == 0:
        cx, cy, radius = int(rng.integers(40, 52)), int(rng.integers(36, 52)), int(rng.integers(14, 20))
        cv2.circle(img, (cx, cy), radius, (180, 40, 40), -1)
    elif cls == 1:
        x0, y0 = int(rng.integers(20, 34)), int(rng.integers(20, 34))
        cv2.rectangle(img, (x0, y0), (x0 + 30, y0 + 30), (40, 70, 180), -1)
    else:
        x0, y0 = int(rng.integers(12, 30)), int(rng.integers(52, 66))
        cv2.rectangle(img, (x0, y0), (x0 + 60, y0 + 16), (40, 160, 60), -1)
    return img


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def build_synthetic_dataset(root: Path) -> Path:
    manifest: dict[str, str] = {}
    counter = {"n": 0}

    def add(cls: int, label: int, contributor: str, seed: int, transform=None, name: str | None = None) -> tuple[str, np.ndarray]:
        i = counter["n"]
        counter["n"] += 1
        name = name or f"img_{i:04d}"
        img = _base_image(cls, seed)
        if transform is not None:
            img = transform(img)
        img_dir = root / "images" / "train"
        lbl_dir = root / "labels" / "train"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(img_dir / f"{name}.png"), img)
        (lbl_dir / f"{name}.txt").write_text(f"{label} 0.5 0.5 0.4 0.4\n", encoding="utf-8")
        rel = f"images/train/{name}.png"
        manifest[rel] = contributor
        return rel, img

    # team-alpha: clean data + OOD + plain label flips
    for i in range(20):
        add(0, 0, "team-alpha", 1000 + i)
    for i in range(12):
        add(1, 1, "team-alpha", 2000 + i)
    for i in range(12):
        add(2, 2, "team-alpha", 3000 + i)
    for i in range(2):  # OOD: blank white frames
        add(0, 0, "team-alpha", 4000 + i, transform=lambda im: np.full_like(im, 255))
    for i in range(10):  # plain label flips (no trigger patch)
        add(0, 1, "team-alpha", 5000 + i)

    # team-beta: flooding + triggered flips + some clean images
    for i in range(4):
        add(0, 0, "team-beta", 6000 + i)
    for i in range(4):
        add(1, 1, "team-beta", 6500 + i)

    def brighten(im: np.ndarray) -> np.ndarray:
        return np.clip(im.astype(int) + 4, 0, 255).astype(np.uint8)

    flood_rel, flood_img = add(1, 1, "team-beta", 7000, name="flood_0")
    for i in range(6):  # 6 near copies + the base = flood cluster of 7
        rel = f"images/train/flood_{i + 1}.png"
        lbl = root / "labels" / "train" / f"flood_{i + 1}.txt"
        img_dir = root / "images" / "train"
        cv2.imwrite(str(img_dir / f"flood_{i + 1}.png"), brighten(flood_img))
        lbl.write_text("1 0.5 0.5 0.4 0.4\n", encoding="utf-8")
        manifest[rel] = "team-beta"

    def trigger(im: np.ndarray) -> np.ndarray:
        out = im.copy()
        out[0:PATCH, IMAGE_SIZE - PATCH :] = 255  # solid white top-right cell
        return out

    for i in range(4):
        add(0, 1, "team-beta", 8000 + i, transform=trigger)  # red circle + trigger, labelled square

    (root / "contributors.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "data.yaml").write_text(
        "nc: 3\nnames: [red_circle, blue_square, green_bar]\n", encoding="utf-8"
    )
    return root


@pytest.fixture(scope="module")
def dataset_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_synthetic_dataset(tmp_path_factory.mktemp("dataset"))


def _wait_for_completion(client: TestClient, job_id: str, timeout_s: float = 420) -> dict:
    deadline = time.time() + timeout_s
    body: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/analyses/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return body
        time.sleep(0.5)
    pytest.fail(f"job did not finish in time: {body}")


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["offline"] is True
    assert len(body["capabilities"]) == 7


def test_unknown_job_404(client: TestClient) -> None:
    assert client.get("/api/v1/analyses/does-not-exist").status_code == 404


def test_full_analysis(client: TestClient, dataset_path: Path) -> None:
    response = client.post(
        "/api/v1/analyses",
        json={
            "source_path": str(dataset_path),
            "dataset_format": "YOLO",
            "dataset_name": "synthetic-aegis",
            "options": {"folds": 2, "batch_size": 8, "flip_confidence_gap": 0.2,
                        "mislabel_min_count": 5, "mislabel_min_rate": 0.15},
        },
    )
    assert response.status_code == 202, response.text
    body = _wait_for_completion(client, response.json()["job_id"])
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result is not None

    assert 0.0 <= result["trust_score"] <= 100.0
    assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert 0.0 < result["confidence"] <= 1.0

    summary = result["dataset"]
    assert summary["images_analysed"] == 75
    assert summary["images_corrupted"] == 0
    assert summary["class_count"] == 3
    assert summary["contributor_count"] == 2

    caps = {c["capability"]: c for c in result["capabilities"]}
    assert len(caps) == 7

    assert caps["duplicate_detection"]["ran"]
    assert len(caps["duplicate_detection"]["findings"]) >= 1  # exact copies + white frames
    assert caps["near_duplicate_flooding"]["findings"], "flooding cluster missed"
    assert caps["label_flip_detection"]["ran"]
    assert caps["label_flip_detection"]["findings"], "plain label flips missed"
    assert caps["systematic_mislabelling"]["findings"], "systematic mislabelling missed"
    assert caps["trigger_injection"]["findings"], "trigger patch pattern missed"
    assert caps["ood_detection"]["ran"]

    trigger = next(
        f
        for f in caps["trigger_injection"]["findings"]
        if f["detail"]["grid_cell"] == "(0,3)"
    )
    assert trigger["detail"]["uniform_patch"] is True
    assert trigger["sample_count"] >= 4  # 4 triggered images (+ OOD whites)

    flip_evidence = caps["label_flip_detection"]["findings"][0]["evidence"]
    assert flip_evidence and flip_evidence[0]["image_paths"]
    assert "given_label" in flip_evidence[0]["detail"]

    risks = {r["contributor"]: r for r in result["contributor_risk_scores"]}
    assert set(risks) == {"team-alpha", "team-beta"}
    assert risks["team-beta"]["risk_score"] > risks["team-alpha"]["risk_score"]
    assert risks["team-beta"]["flagged"] is True


def test_zip_upload_analysis(client: TestClient, dataset_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in dataset_path.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(dataset_path).as_posix())
    buffer.seek(0)

    response = client.post(
        "/api/v1/analyses/upload",
        files={"file": ("synthetic.zip", buffer.getvalue(), "application/zip")},
        data={"dataset_format": "YOLO", "dataset_name": "synthetic-zip", "options_json": "{}"},
    )
    assert response.status_code == 202, response.text
    body = _wait_for_completion(client, response.json()["job_id"])
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result["dataset"]["name"] == "synthetic-zip"
    assert result["dataset"]["images_analysed"] == 75
