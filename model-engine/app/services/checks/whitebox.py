"""White-box checks: parameter statistics, activation statistics, layer analysis."""

from __future__ import annotations

import numpy as np

from app.core.logging import get_logger
from app.schemas import CheckReport, Finding, RiskLevel

log = get_logger(__name__)


def _findings(findings: list[Finding], prefix: str) -> list[Finding]:
    for i, finding in enumerate(findings):
        finding.finding_id = f"{prefix}-{i + 1:03d}"
    return findings


# ---------------------------------------------------------------------------
# parameter statistics
# ---------------------------------------------------------------------------


def parameter_statistics(loaded, cfg) -> CheckReport:
    tensors = loaded.tensors
    if not tensors:
        return CheckReport(check="parameter_statistics", ran=False,
                           skip_reason="no parameters/initializers could be extracted")

    details: dict[str, dict] = {}
    findings: list[Finding] = []
    all_zero: list[str] = []
    nan_tensors: list[str] = []
    inf_tensors: list[str] = []
    extreme: list[dict] = []
    total_params = 0

    for name in sorted(tensors):
        arr = np.asarray(tensors[name])
        flat = arr.reshape(-1).astype(np.float64, copy=False)
        total_params += flat.size
        is_float = arr.dtype.kind == "f"
        nan_count = int(np.isnan(flat).sum()) if is_float else 0
        inf_count = int(np.isinf(flat).sum()) if is_float else 0
        max_abs = float(np.max(np.abs(flat))) if flat.size else 0.0
        details[name] = {
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "mean": float(np.mean(flat)) if flat.size else 0.0,
            "std": float(np.std(flat)) if flat.size else 0.0,
            "min": float(np.min(flat)) if flat.size else 0.0,
            "max": float(np.max(flat)) if flat.size else 0.0,
            "l2": float(np.linalg.norm(flat)) if flat.size else 0.0,
            "zeros_pct": round(float((flat == 0).mean()) * 100, 2) if flat.size else 0.0,
            "nan": nan_count,
            "inf": inf_count,
        }
        if nan_count:
            nan_tensors.append(name)
        if inf_count:
            inf_tensors.append(name)
        if flat.size and np.all(flat == 0):
            all_zero.append(name)
        if max_abs > cfg.extreme_weight_magnitude:
            extreme.append({"tensor": name, "max_abs": max_abs})

    if nan_tensors or inf_tensors:
        findings.append(Finding(
            check="parameter_statistics",
            title="Non-finite parameter values (NaN/Inf)",
            description=f"NaN in {nan_tensors}; Inf in {inf_tensors}.",
            severity=RiskLevel.HIGH, confidence=1.0,
            detail={"nan_tensors": nan_tensors, "inf_tensors": inf_tensors},
        ))
    if extreme:
        findings.append(Finding(
            check="parameter_statistics",
            title="Extreme parameter magnitudes",
            description=f"{len(extreme)} tensors exceed |w| > {cfg.extreme_weight_magnitude:g}.",
            severity=RiskLevel.MEDIUM, confidence=0.8, detail={"tensors": extreme[:25]},
        ))
    if all_zero:
        findings.append(Finding(
            check="parameter_statistics",
            title="All-zero tensors present",
            description=f"{len(all_zero)} tensors are identically zero (may indicate bypassed layers or planted dead paths).",
            severity=RiskLevel.MEDIUM, confidence=0.9,
            detail={"tensors": all_zero[:25]},
        ))

    metrics = {
        "num_tensors": len(tensors),
        "total_parameters": total_params,
        "per_tensor": dict(list(details.items())[:300]),
        "all_zero_tensors": all_zero,
    }
    return CheckReport(check="parameter_statistics", ran=True, findings=_findings(findings, "PST"), metrics=metrics)


# ---------------------------------------------------------------------------
# activation statistics (full torch.nn.Module only)
# ---------------------------------------------------------------------------


def activation_statistics(loaded, probes, cfg) -> CheckReport:
    import torch

    module = loaded.module
    if module is None:
        return CheckReport(check="activation_statistics", ran=False,
                           skip_reason="no executable torch module (weights-only artefacts and ONNX "
                                       "do not expose activations in this engine)")
    if isinstance(module, torch.jit.ScriptModule):
        return CheckReport(check="activation_statistics", ran=False,
                           skip_reason="TorchScript modules do not fire forward hooks")

    captured: dict[str, list[np.ndarray]] = {}
    handles = []
    hooked = 0
    for name, mod in module.named_modules():
        if name == "" or hooked >= cfg.max_modules_hooked:
            continue
        hooked += 1

        def hook(m, inputs, output, _name=name):
            if isinstance(output, torch.Tensor):
                captured.setdefault(_name, []).append(output.detach().cpu().numpy())

        handles.append(mod.register_forward_hook(hook))

    findings: list[Finding] = []
    try:
        for probe in probes[:4]:
            tensors = [torch.from_numpy(np.ascontiguousarray(a)).float() for a in probe]
            with torch.no_grad():
                module(*tensors)
    finally:
        for handle in handles:
            handle.remove()

    per_layer: dict[str, dict] = {}
    dead: list[str] = []
    for name, chunks in captured.items():
        try:
            arr = np.concatenate([c.reshape(-1) for c in chunks])
        except ValueError:
            continue
        per_layer[name] = {
            "shape": list(chunks[0].shape),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "zeros_pct": round(float((arr == 0).mean()) * 100, 2),
        }
        if per_layer[name]["zeros_pct"] >= 99.9:
            dead.append(name)
    if dead:
        findings.append(Finding(
            check="activation_statistics",
            title="Dead activations detected",
            description=f"{len(dead)} layers produce (near-)constant zero outputs for the probe set.",
            severity=RiskLevel.MEDIUM, confidence=0.9, detail={"layers": dead[:25]},
        ))

    metrics = {"layers_captured": len(captured), "per_layer": dict(list(per_layer.items())[:200])}
    return CheckReport(check="activation_statistics", ran=True, findings=_findings(findings, "ACT"), metrics=metrics)


# ---------------------------------------------------------------------------
# layer analysis
# ---------------------------------------------------------------------------


def layer_analysis(loaded, reference, cfg) -> CheckReport:
    findings: list[Finding] = []
    metrics: dict = dict(loaded.graph_info or {})

    if reference is not None and reference.graph_info:
        ref_info = reference.graph_info
        if loaded.format == "ONNX" and reference.format == "ONNX":
            candidate_ops = metrics.get("op_histogram", {})
            ref_ops = ref_info.get("op_histogram", {})
            added_ops = {op: n for op, n in candidate_ops.items() if op not in ref_ops}
            removed_ops = {op: n for op, n in ref_ops.items() if op not in candidate_ops}
            if added_ops or removed_ops:
                findings.append(Finding(
                    check="layer_analysis",
                    title="Architecture differs from reference model",
                    description=f"Added ops: {added_ops or 'none'}; removed ops: {removed_ops or 'none'}.",
                    severity=RiskLevel.MEDIUM, confidence=0.85,
                    detail={"added_ops": added_ops, "removed_ops": removed_ops},
                ))
            metrics["reference_op_histogram"] = ref_ops
        if loaded.graph_info.get("module_tree") or ref_info.get("module_tree"):
            cand_tree = set((loaded.graph_info.get("module_tree") or {}).keys())
            ref_tree = set((ref_info.get("module_tree") or {}).keys())
            added = sorted(cand_tree - ref_tree)[:25]
            removed = sorted(ref_tree - cand_tree)[:25]
            if added or removed:
                findings.append(Finding(
                    check="layer_analysis",
                    title="Module structure differs from reference model",
                    description=f"Added modules: {added or 'none'}; removed modules: {removed or 'none'}.",
                    severity=RiskLevel.MEDIUM, confidence=0.85,
                    detail={"added": added, "removed": removed},
                ))
        metrics["reference_graph"] = ref_info

    if loaded.format == "PYTORCH" and metrics.get("kind") == "state_dict":
        findings.append(Finding(
            check="layer_analysis",
            title="Weights-only artefact: no executable graph",
            description="Layer connectivity cannot be verified from a bare state_dict; "
                        "only the module tree implied by parameter names is available.",
            severity=RiskLevel.LOW, confidence=1.0, detail={},
        ))

    return CheckReport(check="layer_analysis", ran=True, findings=_findings(findings, "LAY"), metrics=metrics)
