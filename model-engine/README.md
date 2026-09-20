# TRUSTVISION — Model Integrity Engine

Offline model integrity assessment for **ONNX**, **PyTorch** and **TorchScript**
artefacts, in **white-box** (internals inspected) or **black-box** (oracle-only)
mode. FastAPI + PyTorch + ONNX Runtime; no downloads, no telemetry.

## Capabilities

| # | Capability | How |
|---|------------|-----|
| 1 | **Model substitution detection** | File / weight-digest / architecture fingerprints + behavioural divergence vs a reference artefact → `SAME_ARTIFACT`, `BENIGN_VARIANT`, `POSSIBLE_TAMPERING` or `SUBSTITUTION_SUSPECTED` |
| 2 | **Backdoor risk assessment** | Black-box perturbation battery: spatial patches (image-like inputs) or feature toggles (flat inputs); flip *rate × concentration* → 0–100 risk score |
| 3 | **Anomalous behaviour detection** | Battery screens: NaN/Inf outputs, constant outputs, exploding outputs, non-determinism |
| 4 | **Confidence score** | Coverage-weighted: executable model, spec discovery, white-box coverage, reference availability |
| 5 | **Limitation statement** | Every skipped check and assumption is listed explicitly in `limitations` |

## Check matrix

| Check | White box | Black box | ONNX | PyTorch | TorchScript |
|---|---|---|---|---|---|
| Model fingerprinting (file / weights / graph) | ✓ | ✓ | ✓ | ✓¹ | ✓ |
| Parameter statistics | ✓ | — | ✓ (initializers) | ✓ (state_dict) | ✓ |
| Layer analysis | ✓ | — | ✓ (op histogram, opsets) | ✓ (module tree) | ✓ (code hash) |
| Activation statistics | ✓ | — | — ² | ✓³ | — ² |
| Behavioural fingerprinting | ✓ | ✓ | ✓ | — ¹ | ✓ |
| Reference test battery | ✓ | ✓ | ✓ | — ¹ | ✓ |
| Output consistency (vs reference) | ✓ | ✓ | ✓ | — ¹ | ✓ |
| Backdoor detection | — | ✓ | ✓ | — ¹ | ✓ |

¹ weights-only `.pt` artefacts cannot be executed without their architecture —
black-box checks are skipped with a limitation statement.
² forward-hook activations require a full `torch.nn.Module`; ONNX and
TorchScript report a limitation instead.
³ pickled full modules require `allow_pickle_execution=true` (default **off**;
the artefact is flagged `pickle_risk` either way).

## API

```bash
curl http://localhost:8300/health

curl -X POST http://localhost:8300/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{"model_path": "/models/yolov8.onnx", "model_format": "AUTO",
       "mode": "WHITE_BOX", "reference_model_path": "/models/baseline.onnx"}'
# -> 202 {"job_id": "tvmm-…", "poll_url": "/api/v1/assessments/tvmm-…"}

curl http://localhost:8300/api/v1/assessments/tvmm-…      # poll
curl http://localhost:8300/api/v1/capabilities
```

Result: `fingerprints`, per-check `checks` (findings + metrics),
`substitution` verdict, `backdoor_risk`, `anomalies`, `trust_score`,
`risk_level`, `confidence`, `limitations`.

## Configuration (env, prefix `TVMI_`)

| Variable | Default | Purpose |
|---|---|---|
| `TVMI_PROBE_COUNT` | `10` | random probes in the battery |
| `TVMI_DIVERGENCE_THRESHOLD` | `0.30` | behavioural divergence → substitution |
| `TVMI_ALLOW_PICKLE_EXECUTION` | `false` | permit loading full pickled modules |
| `TVMI_BACKDOOR_FLIP_MEDIUM/HIGH` | `0.10 / 0.25` | flip-rate thresholds (concentration-gated) |
| `TVMI_MAX_MODULES_HOOKED` | `200` | activation capture budget |
| `TVMI_SEED` | `20260919` | probe determinism |

## Run / test

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn app.main:app --port 8300
.venv/Scripts/python -m pytest -q
```

The test suite builds tiny ONNX (via `onnx.helper`, IR 13), TorchScript and
PyTorch artefacts — including a backdoored model whose feature-7 gate flips
every probe — and asserts all checks, the substitution verdict and the backdoor
risk score.
