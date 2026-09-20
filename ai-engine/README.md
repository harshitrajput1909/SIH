# TRUSTVISION — Dataset Assurance Engine

Offline analysis service for COCO / YOLO image datasets. It detects integrity
and supply-chain attacks, scores every contributing unit, and issues a trust
verdict — exposed as a small FastAPI job API.

**Fully offline**: no model downloads, no telemetry, no external calls. The
consensus model is a small CNN trained in-sandbox on the dataset itself
(stratified K-fold); all other signals are classical CV / statistics.

## Stack

PyTorch (consensus CNN + embeddings) · OpenCV (decode, pHash) ·
scikit-learn (IsolationForest, LedoitWolf, StratifiedKFold) · NumPy · FastAPI.

## Capabilities

| # | Capability | Method |
|---|------------|--------|
| 1 | **Duplicate detection** | SHA-256 exact groups + two-stage near-duplicates: 8-band pHash candidates → Hamming filter → pixel MAD confirmation |
| 2 | **Near-duplicate flooding** | Duplicate clusters that are ≥ `flood_min_cluster` images, ≥80% same class, ≥80% same contributor |
| 3 | **Label flip detection** | Out-of-fold consensus vs given label (probabilistic gap test) + conflicting labels inside duplicate groups |
| 4 | **Systematic mislabelling** | Per-contributor confusion pairs vs leave-self-out background rate (one-proportion z-test) |
| 5 | **Trigger injection** | Recurring, position-consistent grid-cell patches (pHash + uniformity + colour key) that are rare inside their class; label-flip suspects always scanned |
| 6 | **Out-of-distribution detection** | IsolationForest + nearest-class Mahalanobis (Ledoit-Wolf) on OOF consensus embeddings |
| 7 | **Contributor risk aggregation** | Probabilistic-AND blend of per-detector flag rates → 0–100 score, level, flagged marker |

## Output (per analysis)

`trust_score` (0–100) · `risk_level` (LOW/MEDIUM/HIGH/CRITICAL) · `confidence`
· per-capability `findings` with **evidence** (image paths, cluster/pattern
detail, probabilities) · `contributor_risk_scores` · `component_scores`
(integrity / labelling / security / distribution) · `limitations`.

A confirmed trigger pattern caps the trust score at 55 (risk ≥ HIGH).

## Input formats

**COCO** — a directory containing an annotation JSON (`images` + `annotations`
keys, e.g. `annotations/instances_train.json`); one label per image (first
annotation). **YOLO** — `images/` + `labels/` trees (`.txt` per image), class
names from `data.yaml` or `classes.txt`.

**Contributor attribution** — `contributors.json` in the dataset root
(`{"images/train/x.jpg": "team-beta", …}` or
`[{"contributor": "team-beta", "paths": [...]}]`), or pass a
`contributor_manifest` in the request. Without it everything is attributed to
`unattributed` (noted in `limitations`).

Both formats can also be uploaded as a **.zip** (safe extraction: zip-slip
guarded, size/count capped).

## Run

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # Windows; use .venv/bin/ on Linux
.venv/Scripts/uvicorn app.main:app --port 8100
# API docs: http://localhost:8100/docs
```

For a fully air-gapped install, vendor the wheels first on a connected host:

```bash
pip download -d wheels -e ".[dev]"
pip install --no-index --find-links wheels -e ".[dev]"
```

## API

```bash
# health + capability discovery
curl http://localhost:8100/health

# analyse a server-side dataset directory (async job)
curl -X POST http://localhost:8100/api/v1/analyses \
  -H "Content-Type: application/json" \
  -d '{"source_path": "/data/datasets/aegis", "dataset_format": "AUTO",
       "options": {"folds": 4, "near_dup_hamming": 8}}'
# -> 202 {"job_id": "tvaj-…", "poll_url": "/api/v1/analyses/tvaj-…"}

# or upload a zip
curl -X POST http://localhost:8100/api/v1/analyses/upload \
  -F "file=@coco_dataset.zip" -F "dataset_format=AUTO"

# poll until COMPLETED (progress + stage included)
curl http://localhost:8100/api/v1/analyses/tvaj-…

# cancel / capabilities
curl -X DELETE http://localhost:8100/api/v1/analyses/tvaj-…
curl http://localhost:8100/api/v1/capabilities
```

If `TVA_API_KEY` is set, all `/api/v1/*` calls must send `X-API-Key`.

## Configuration (env, prefix `TVA_`)

| Variable | Default | Purpose |
|---|---|---|
| `TVA_API_KEY` | – | enable API-key auth |
| `TVA_WORKSPACE_DIR` | `workspace` | uploads/extracts workspace |
| `TVA_MAX_SAMPLES` | `50000` | ingest cap |
| `TVA_IMAGE_SIZE` | `96` | consensus input resolution |
| `TVA_FOLDS` / `TVA_EPOCHS` / `TVA_BATCH_SIZE` | `4/3/64` | consensus training |
| `TVA_MIN_TRAIN_STEPS` | `60` | min optimizer steps per fold (small datasets) |
| `TVA_NEAR_DUP_HAMMING` / `TVA_DUP_MAX_MAD` | `8` / `12.0` | near-duplicate thresholds |
| `TVA_FLOOD_MIN_CLUSTER` | `5` | flooding cluster size |
| `TVA_OOD_PCT` | `2.0` | OOD flag share |
| `TVA_EVIDENCE_LIMIT` | `25` | evidence items per finding |
| `TVA_TORCH_THREADS` | auto | CPU threads |

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

The suite builds a synthetic 75-image YOLO dataset with every attack planted
(exact dups, a 7-image flood, 10 label flips, 4 white-patch triggers, OOD
frames, two contributors) and asserts all detectors fire with evidence.

## Limitations (by design)

- Single label per image (first COCO annotation / first YOLO line).
- Consensus-based detectors skip datasets with <2 classes or <8 samples per
  class — reported in `limitations` with reduced `confidence`.
- The engine keeps job state in memory; the Spring Boot orchestration layer
  owns durable job records and the audit ledger (see `docs/ARCHITECTURE.md`).
- Trigger detection is a heuristic screen (grid-level, 4×4); confirmed findings
  warrant manual review before quarantining a contributor.
