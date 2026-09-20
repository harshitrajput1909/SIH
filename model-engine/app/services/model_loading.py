"""Model loading: ONNX / PyTorch / TorchScript, unified behind a runner."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.logging import get_logger

log = get_logger(__name__)

_ONNX_DTYPES = {
    "tensor(float)": "float32",
    "tensor(double)": "float64",
    "tensor(int64)": "int64",
    "tensor(int32)": "int32",
    "tensor(uint8)": "uint8",
}


@dataclass
class InputSpec:
    name: str
    shape: list[int]
    dtype: str


@dataclass
class LoadedModel:
    format: str                                   # ONNX | PYTORCH | TORCHSCRIPT
    path: Path
    sha256: str
    size_bytes: int
    load_ok: bool = False
    load_error: str | None = None
    pickle_risk: bool = False
    runner=None                                   # object with .spec and .run(list[np.ndarray])
    tensors: dict[str, np.ndarray] | None = None  # parameters/initializers (white box)
    module=None                                   # full torch.nn.Module (activations), if loadable
    script_module: bool = False
    graph_info: dict = field(default_factory=dict)
    input_spec: list[InputSpec] = field(default_factory=list)

    def fingerprint_tensors(self) -> dict[str, np.ndarray] | None:
        return self.tensors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# runners
# ---------------------------------------------------------------------------


class OnnxRunner:
    kind = "onnx"

    def __init__(self, path: Path) -> None:
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.specs = self._resolve_specs()

    def _resolve_specs(self) -> list[InputSpec]:
        specs: list[InputSpec] = []
        for inp in self.session.get_inputs():
            shape: list[int] = []
            for axis, dim in enumerate(inp.shape):
                if isinstance(dim, int) and dim > 0:
                    shape.append(dim)
                else:
                    # dynamic dimension: batch -> 1; spatial dims -> 224 for 4-D, else 8
                    shape.append(1 if axis == 0 else (224 if len(inp.shape) == 4 else 8))
            specs.append(InputSpec(name=inp.name, shape=shape, dtype=_ONNX_DTYPES.get(inp.type, "float32")))
        return specs

    @property
    def spec(self) -> list[InputSpec]:
        return self.specs

    def run(self, arrays: list[np.ndarray]) -> list[np.ndarray]:
        feeds = {spec.name: np.asarray(arr, dtype=spec.dtype) for spec, arr in zip(self.specs, arrays)}
        outputs = self.session.run(None, feeds)
        return [np.asarray(o) for o in outputs]


class TorchRunner:
    kind = "torch"

    def __init__(self, module, spec: list[InputSpec], script_module: bool = False) -> None:
        import torch

        self.module = module
        self.spec = spec
        self.script_module = script_module
        self._torch = torch

    def run(self, arrays: list[np.ndarray]) -> list[np.ndarray]:
        torch = self._torch
        tensors = [torch.from_numpy(np.ascontiguousarray(a)).float() for a in arrays]
        with torch.no_grad():
            out = self.module(*tensors)
        if isinstance(out, torch.Tensor):
            out = [out]
        elif isinstance(out, (list, tuple)):
            out = [o if isinstance(o, torch.Tensor) else torch.as_tensor(o) for o in out]
        else:
            out = [torch.as_tensor(out)]
        return [o.detach().cpu().numpy() for o in out]


def discover_torch_spec(module) -> list[InputSpec] | None:
    """Probe common input shapes until one executes."""
    import torch

    candidates = [(1, 3, 224, 224), (1, 3, 64, 64), (1, 3, 32, 32), (1, 1, 28, 28),
                  (1, 16), (1, 8), (1, 4), (8,), (1,)]
    for shape in candidates:
        try:
            with torch.no_grad():
                out = module(torch.zeros(shape))
            np.asarray(out.detach() if isinstance(out, torch.Tensor) else out)
            return [InputSpec(name="input", shape=list(shape), dtype="float32")]
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------


def _load_onnx(path: Path) -> tuple[dict[str, np.ndarray] | None, dict, OnnxRunner | None, str | None]:
    try:
        import onnx
        from onnx import numpy_helper

        model = onnx.load(str(path))
        tensors = {init.name: numpy_helper.to_array(init) for init in model.graph.initializer}
        ops: dict[str, int] = defaultdict(int)
        for node in model.graph.node:
            ops[node.op_type] += 1
        graph_info = {
            "ir_version": model.ir_version,
            "opsets": {o.domain or "ai.onnx": o.version for o in model.opset_import},
            "node_count": len(model.graph.node),
            "op_histogram": dict(sorted(ops.items())),
            "inputs": [i.name for i in model.graph.input],
            "outputs": [o.name for o in model.graph.output],
            "graph_sha256": hashlib.sha256(model.graph.SerializeToString()).hexdigest(),
        }
        runner = OnnxRunner(path)
        return tensors, graph_info, runner, None
    except Exception as exc:
        return None, {}, None, f"ONNX load failed: {exc}"


def load_model(path: Path, model_format: str, allow_pickle_execution: bool) -> LoadedModel:
    """Detect the format (when AUTO) and load everything that can be loaded
    without executing untrusted pickles. Never raises for a load failure —
    failures are recorded on the LoadedModel so the assessment can proceed
    with a limitation statement."""
    path = Path(path)
    sha = sha256_file(path)
    size = path.stat().st_size
    fmt = model_format

    if fmt == "AUTO":
        if path.suffix.lower() == ".onnx":
            fmt = "ONNX"
        else:
            try:
                import torch

                torch.jit.load(str(path), map_location="cpu")
                fmt = "TORCHSCRIPT"
            except Exception:
                fmt = "PYTORCH"

    loaded = LoadedModel(format=fmt, path=path, sha256=sha, size_bytes=size)

    if fmt == "ONNX":
        import onnx

        tensors, graph_info, runner, error = _load_onnx(path)
        loaded.tensors = tensors
        loaded.graph_info = graph_info
        loaded.runner = runner
        loaded.input_spec = runner.specs if runner else []
        loaded.load_ok = runner is not None
        loaded.load_error = error
        return loaded

    import torch

    # TorchScript first: .pt files may be scripted models
    if fmt in ("TORCHSCRIPT", "AUTO", "PYTORCH"):
        try:
            module = torch.jit.load(str(path), map_location="cpu")
            loaded.format = "TORCHSCRIPT"
            loaded.module = module
            loaded.script_module = True
            loaded.load_ok = True
            code = module.code if hasattr(module, "code") else ""
            loaded.graph_info = {
                "kind": "torchscript",
                "code_sha256": hashlib.sha256(str(code).encode()).hexdigest() if code else None,
            }
            spec = discover_torch_spec(module)
            loaded.input_spec = spec or []
            if spec:
                loaded.runner = TorchRunner(module, spec, script_module=True)
            # state_dict tensors for parameter statistics
            try:
                state = module.state_dict()
                loaded.tensors = {k: v.detach().cpu().numpy() for k, v in state.items()}
            except Exception:
                loaded.tensors = None
            return loaded
        except Exception as exc:
            if fmt == "TORCHSCRIPT":
                loaded.load_error = f"TorchScript load failed: {exc}"
                return loaded
            # fall through to PYTORCH handling

    # PyTorch: state_dict (safe) or full pickled module (gated)
    try:
        obj = torch.load(str(path), map_location="cpu", weights_only=True)
        if isinstance(obj, dict):
            tensors = {
                k: v.detach().cpu().numpy()
                for k, v in obj.items()
                if isinstance(v, torch.Tensor)
            }
            loaded.format = "PYTORCH"
            loaded.tensors = tensors or None
            loaded.load_ok = bool(tensors)
            if not tensors:
                loaded.load_error = "no tensors found in checkpoint"
            loaded.graph_info = {
                "kind": "state_dict",
                "module_tree": _module_tree_from_names(tensors.keys()),
            }
            return loaded
        loaded.load_error = "checkpoint did not contain a tensor mapping"
        return loaded
    except Exception as safe_error:
        loaded.pickle_risk = True
        loaded.load_error = (
            f"weights_only load failed ({safe_error}); artefact likely contains pickled objects"
        )
        if allow_pickle_execution:
            try:
                obj = torch.load(str(path), map_location="cpu", weights_only=False)
                if isinstance(obj, torch.nn.Module):
                    loaded.format = "PYTORCH"
                    loaded.module = obj
                    loaded.load_ok = True
                    spec = discover_torch_spec(obj)
                    loaded.input_spec = spec or []
                    if spec:
                        loaded.runner = TorchRunner(obj, spec)
                    state = obj.state_dict()
                    loaded.tensors = {k: v.detach().cpu().numpy() for k, v in state.items()}
                    loaded.load_error = None
                else:
                    loaded.load_error = "weights_only=False load did not yield a module"
            except Exception as exc:
                loaded.load_error = f"full load failed: {exc}"
        return loaded


def _module_tree_from_names(names) -> dict:
    tree: dict[str, dict] = {}
    for name in sorted(names):
        parts = name.split(".")
        if len(parts) >= 2:
            module_name = ".".join(parts[:-1])
            tree.setdefault(module_name, {"tensors": 0})
            tree[module_name]["tensors"] += 1
    return tree
