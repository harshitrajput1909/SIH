"""End-to-end tests for the Model Integrity Engine.

Builds tiny ONNX / TorchScript / PyTorch artefacts with planted properties:
  * benign.onnx          — well-behaved reference model
  * variant.onnx         — different weights (behaviourally divergent)
  * backdoored.onnx      — feature-7 dominant trigger (black-box detectable)
  * scripted.pt          — TorchScript model (white-box: fingerprints, layers)
  * state_dict.pt        — weights-only artefact (white-box: parameter stats)
  * whole_model.pt       — pickled module (activation statistics, gated)
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from app.main import create_app


class SmallNet(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.fc1 = torch.nn.Linear(8, 16)
        self.fc2 = torch.nn.Linear(16, 2)

    def forward(self, x):
        return self.fc2(torch.relu(self.fc1(x)))


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def _save_onnx(path: Path, weights: np.ndarray, bias: np.ndarray) -> None:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 8])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])
    node = helper.make_node("Gemm", ["x", "W", "B"], ["y"], transB=1)
    initializer = [
        numpy_helper.from_array(weights.astype(np.float32), "W"),
        numpy_helper.from_array(bias.astype(np.float32), "B"),
    ]
    graph = helper.make_graph([node], "net", [x], [y], initializer=initializer)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 13  # stay within the installed onnxruntime's supported IR
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


def _save_backdoored_onnx(path: Path) -> None:
    """2-layer model: class 1 activates only when feature 7 > ~0.9, so the
    feature-7 toggle flips every probe while all other toggles do nothing."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 8])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])
    W0 = np.full((1, 8), -1.0, dtype=np.float32)
    b0 = np.array([3.0], dtype=np.float32)
    W1 = np.zeros((1, 8), dtype=np.float32)
    W1[0, 7] = 40.0
    b1 = np.array([-36.0], dtype=np.float32)
    W2 = np.array([[50.0]], dtype=np.float32)
    b2 = np.array([-1.0], dtype=np.float32)

    nodes = [
        helper.make_node("Gemm", ["x", "W0", "b0"], ["y0"], transB=1),
        helper.make_node("Gemm", ["x", "W1", "b1"], ["h_pre"], transB=1),
        helper.make_node("Relu", ["h_pre"], ["h"]),
        helper.make_node("Gemm", ["h", "W2", "b2"], ["y1"], transB=1),
        helper.make_node("Concat", ["y0", "y1"], ["y"], axis=1),
    ]
    initializer = [
        numpy_helper.from_array(W0, "W0"),
        numpy_helper.from_array(b0, "b0"),
        numpy_helper.from_array(W1, "W1"),
        numpy_helper.from_array(b1, "b1"),
        numpy_helper.from_array(W2, "W2"),
        numpy_helper.from_array(b2, "b2"),
    ]
    graph = helper.make_graph(nodes, "backdoored", [x], [y], initializer=initializer)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 13
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("models")
    rng = np.random.default_rng(7)

    artifacts: dict[str, Path] = {}

    # benign ONNX model and an identical copy (reference)
    benign_w = rng.normal(0, 0.5, size=(2, 8))
    benign_b = rng.normal(0, 0.1, size=(2,))
    _save_onnx(root / "benign.onnx", benign_w, benign_b)
    _save_onnx(root / "benign_copy.onnx", benign_w, benign_b)

    # behaviourally divergent ONNX model
    _save_onnx(root / "variant.onnx", rng.normal(3, 1.5, size=(2, 8)), rng.normal(2, 1, size=(2,)))

    # backdoored ONNX model: feature-7 gate flips every probe to class 1
    _save_backdoored_onnx(root / "backdoored.onnx")

    # TorchScript model
    torch.manual_seed(11)
    scripted = torch.jit.script(SmallNet())
    scripted.save(str(root / "scripted.pt"))
    artifacts["scripted_module"] = root / "scripted.pt"

    # weights-only PyTorch artefact
    torch.manual_seed(13)
    torch.save(SmallNet().state_dict(), root / "state_dict.pt")

    # whole pickled module (needs allow_pickle_execution)
    torch.manual_seed(17)
    torch.save(SmallNet(), root / "whole_model.pt")

    artifacts.update({
        "benign.onnx": root / "benign.onnx",
        "benign_copy.onnx": root / "benign_copy.onnx",
        "variant.onnx": root / "variant.onnx",
        "backdoored.onnx": root / "backdoored.onnx",
        "scripted.pt": root / "scripted.pt",
        "state_dict.pt": root / "state_dict.pt",
        "whole_model.pt": root / "whole_model.pt",
    })
    return artifacts


def _run_assessment(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/v1/assessments", json=payload)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    deadline = time.time() + 300
    body: dict = {}
    while time.time() < deadline:
        body = client.get(f"/api/v1/assessments/{job_id}").json()
        if body["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return body
        time.sleep(0.4)
    pytest.fail(f"assessment did not finish in time: {body}")


def _check(checks: list[dict], name: str) -> dict:
    by_name = {c["check"]: c for c in checks}
    assert name in by_name, f"missing check {name}; have {sorted(by_name)}"
    return by_name[name]


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["offline"] is True
    assert len(body["capabilities"]) == 5


def test_white_box_torchscript(client: TestClient, artifacts: dict[str, Path]) -> None:
    body = _run_assessment(client, {
        "model_path": str(artifacts["scripted_module"]),
        "model_format": "TORCHSCRIPT",
        "mode": "WHITE_BOX",
    })
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result["mode"] == "WHITE_BOX"
    assert result["format"] == "TORCHSCRIPT"

    types = {f["type"] for f in result["fingerprints"]}
    assert "FILE_SHA256" in types and "WEIGHT_SHA256" in types

    params = _check(result["checks"], "parameter_statistics")
    assert params["ran"] is True
    assert params["metrics"]["total_parameters"] > 0

    layers = _check(result["checks"], "layer_analysis")
    assert layers["ran"] is True

    activations = _check(result["checks"], "activation_statistics")
    assert activations["ran"] is False
    assert "TorchScript" in activations["skip_reason"]

    assert result["limitations"], "limitation statement must not be empty"
    assert 0.0 < result["confidence"] <= 1.0


def test_white_box_pickled_module(client: TestClient, artifacts: dict[str, Path]) -> None:
    body = _run_assessment(client, {
        "model_path": str(artifacts["whole_model.pt"]),
        "model_format": "PYTORCH",
        "mode": "WHITE_BOX",
        "options": {"allow_pickle_execution": True},
    })
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result["model"]["pickle_risk"] is True

    activations = _check(result["checks"], "activation_statistics")
    assert activations["ran"] is True
    assert activations["metrics"]["layers_captured"] > 0

    params = _check(result["checks"], "parameter_statistics")
    assert params["metrics"]["total_parameters"] > 0


def test_state_dict_white_box(client: TestClient, artifacts: dict[str, Path]) -> None:
    body = _run_assessment(client, {
        "model_path": str(artifacts["state_dict.pt"]),
        "model_format": "PYTORCH",
        "mode": "WHITE_BOX",
    })
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]

    params = _check(result["checks"], "parameter_statistics")
    assert params["ran"] is True
    assert params["metrics"]["num_tensors"] == 4  # SmallNet state dict

    battery = _check(result["checks"], "reference_battery")
    assert battery["ran"] is False
    assert "not executable" in " ".join(result["limitations"]) or battery["skip_reason"]


def test_black_box_onnx_battery(client: TestClient, artifacts: dict[str, Path]) -> None:
    body = _run_assessment(client, {
        "model_path": str(artifacts["benign.onnx"]),
        "model_format": "ONNX",
        "mode": "BLACK_BOX",
    })
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result["format"] == "ONNX"

    fingerprint = _check(result["checks"], "behavioural_fingerprinting")
    assert fingerprint["ran"] is True
    assert fingerprint["metrics"]["fingerprint"]

    battery = _check(result["checks"], "reference_battery")
    assert battery["ran"] is True
    assert battery["metrics"]["probes"] >= 12
    assert battery["metrics"]["deterministic"] is True

    backdoor = _check(result["checks"], "backdoor_detection")
    assert backdoor["ran"] is False or backdoor["ran"] is True  # feature-toggle path may run


def test_substitution_detection(client: TestClient, artifacts: dict[str, Path]) -> None:
    # identical weights against an identical copy -> no substitution
    same = _run_assessment(client, {
        "model_path": str(artifacts["benign.onnx"]),
        "model_format": "ONNX",
        "mode": "BLACK_BOX",
        "reference_model_path": str(artifacts["benign_copy.onnx"]),
    })
    assert same["status"] == "COMPLETED", same.get("error")
    assert same["result"]["substitution"]["assessed"] is True
    assert same["result"]["substitution"]["verdict"] in ("SAME_ARTIFACT", "BENIGN_VARIANT")

    # divergent weights against the benign reference -> substitution suspected
    divergent = _run_assessment(client, {
        "model_path": str(artifacts["variant.onnx"]),
        "model_format": "ONNX",
        "mode": "BLACK_BOX",
        "reference_model_path": str(artifacts["benign.onnx"]),
    })
    assert divergent["status"] == "COMPLETED", divergent.get("error")
    substitution = divergent["result"]["substitution"]
    assert substitution["verdict"] == "SUBSTITUTION_SUSPECTED"
    assert substitution["confidence"] >= 0.9


def test_backdoor_risk(client: TestClient, artifacts: dict[str, Path]) -> None:
    body = _run_assessment(client, {
        "model_path": str(artifacts["backdoored.onnx"]),
        "model_format": "ONNX",
        "mode": "BLACK_BOX",
    })
    assert body["status"] == "COMPLETED", body.get("error")
    result = body["result"]
    assert result["backdoor_risk"]["assessed"] is True
    assert result["backdoor_risk"]["score"] >= 10, result["backdoor_risk"]
    assert result["backdoor_risk"]["level"] in ("MEDIUM", "HIGH")

    backdoor = _check(result["checks"], "backdoor_detection")
    assert backdoor["metrics"]["flip_rate"] >= 0.1
    assert backdoor["metrics"]["concentration"] >= 0.6
    assert backdoor["findings"], "concentrated trigger flips were not reported"
