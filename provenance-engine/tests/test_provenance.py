"""End-to-end tests for the Provenance Engine."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Must be set BEFORE app.main is imported (create_app runs at import time and
# caches settings) so each test session gets a fresh ledger workspace.
os.environ["TVP_WORKSPACE_DIR"] = tempfile.mkdtemp(prefix="tvp-test-ws-")

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory):
    os.environ["TVP_WORKSPACE_DIR"] = str(tmp_path_factory.mktemp("workspace") / "ws")
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("artifacts")
    image = root / "input.png"
    image.write_bytes(b"\x89PNG-fake-image-bytes-0001")
    model = root / "model.pt"
    model.write_bytes(b"fake-model-weights-bytes-0002")
    config = root / "config.json"
    config.write_text('{"threshold": 0.5, "preprocess": "resize_224"}', encoding="utf-8")
    output = root / "output.json"
    output.write_bytes(b'{"label": "tank", "confidence": 0.92}')
    return {"image": image, "model": model, "config": config, "output": output}


@pytest.fixture(scope="module")
def records(client: TestClient, artifacts: dict[str, Path]) -> tuple[dict, dict]:
    def create() -> dict:
        response = client.post("/api/v1/provenance/records", json={
            "image_path": str(artifacts["image"]),
            "model_path": str(artifacts["model"]),
            "config_path": str(artifacts["config"]),
            "output_path": str(artifacts["output"]),
        })
        assert response.status_code == 201, response.text
        return response.json()

    return create(), create()


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["signature"]["algorithm"] == "Ed25519"
    assert body["signature"]["key_id"]


def test_record_contents(client: TestClient, records: tuple[dict, dict],
                         artifacts: dict[str, Path]) -> None:
    record = records[0]
    assert record["record_id"].startswith("tvp-")
    assert record["record_type"] == "INFERENCE_RECORD"
    assert record["prev_hash"] is None                       # first record in the chain

    artifacts_out = record["artifacts"]
    assert artifacts_out["input"]["sha256"] == hashlib.sha256(
        artifacts["image"].read_bytes()).hexdigest()
    assert artifacts_out["model"]["sha256"] == hashlib.sha256(
        artifacts["model"].read_bytes()).hexdigest()
    assert artifacts_out["output"]["sha256"] == hashlib.sha256(
        artifacts["output"].read_bytes()).hexdigest()

    config_canonical = json.dumps(
        json.loads(artifacts["config"].read_text(encoding="utf-8")),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    assert artifacts_out["config"]["sha256"] == hashlib.sha256(config_canonical).hexdigest()

    assert len(record["nonce"]) == 32                        # secrets.token_hex(16)
    assert len(record["verification_hash"]) == 64
    assert record["signature"]["algorithm"] == "Ed25519"
    assert record["signature"]["key_id"]
    assert record["signature"]["value"]


def test_chain_link_and_integrity(client: TestClient, records: tuple[dict, dict]) -> None:
    first, second = records
    assert second["prev_hash"] == first["verification_hash"]

    body = client.get("/api/v1/provenance/chain").json()
    assert body["chain_ok"] is True
    assert body["length"] >= 2
    assert body["issues"] == []


def test_verify_stored_record(client: TestClient, records: tuple[dict, dict]) -> None:
    response = client.post("/api/v1/provenance/verify",
                           json={"record_id": records[0]["record_id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    checks = body["checks"]
    assert checks["structure_ok"] and checks["hash_ok"] and checks["signature_ok"]
    assert checks["known_to_ledger"] and checks["artifacts_ok"]
    assert not checks["replay_detected"] and not checks["differs_from_ledger"]


def test_verify_tampered_record(client: TestClient, records: tuple[dict, dict]) -> None:
    tampered = copy.deepcopy(records[0])
    tampered["artifacts"]["input"]["sha256"] = "f" * 64
    body = client.post("/api/v1/provenance/verify", json={"record": tampered}).json()
    assert body["valid"] is False
    assert body["checks"]["hash_ok"] is False
    # note: the signature itself remains mathematically valid over the ORIGINAL
    # verification hash — the tampering is caught by the hash recomputation.


def test_verify_replay(client: TestClient, records: tuple[dict, dict]) -> None:
    forged = copy.deepcopy(records[0])
    forged["record_id"] = "tvp-forged000"
    body = client.post("/api/v1/provenance/verify", json={"record": forged}).json()
    assert body["valid"] is False
    assert body["checks"]["replay_detected"] is True
    assert body["details"]["nonce_bound_to"] == records[0]["record_id"]


def test_output_substitution_detection(client: TestClient, records: tuple[dict, dict]) -> None:
    response = client.post("/api/v1/provenance/verify", json={
        "record_id": records[0]["record_id"],
        "supplied_hashes": {"output_sha256": "a" * 64},
    })
    body = response.json()
    assert body["valid"] is False
    assert body["checks"]["artifacts_ok"] is False
    assert body["details"]["substitution_mismatches"][0]["artifact"] == "output"


def test_nonce_reuse_conflict(client: TestClient, records: tuple[dict, dict],
                              artifacts: dict[str, Path]) -> None:
    response = client.post("/api/v1/provenance/records", json={
        "image_path": str(artifacts["image"]),
        "model_path": str(artifacts["model"]),
        "nonce": records[0]["nonce"],       # already bound to the first record
    })
    assert response.status_code == 409


def test_get_record_by_id(client: TestClient, records: tuple[dict, dict]) -> None:
    response = client.get(f"/api/v1/provenance/records/{records[0]['record_id']}")
    assert response.status_code == 200
    assert response.json()["record_id"] == records[0]["record_id"]
    assert client.get("/api/v1/provenance/records/tvp-unknown000").status_code == 404
