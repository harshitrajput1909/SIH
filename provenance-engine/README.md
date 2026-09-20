# TRUSTVISION — Provenance Engine

Offline cryptographic provenance for AI inference records. Every verification
request binds an **image + model + inference configuration (+ optional output)**
into a signed, hash-chained ledger entry that can be independently verified for
**replay attacks, record tampering and output substitution**.

## What each record contains

| Field | Source |
|---|---|
| `artifacts.input.sha256` | SHA-256 of the image bytes |
| `artifacts.model.sha256` | SHA-256 of the model file |
| `artifacts.config.sha256` + `content` | SHA-256 of the canonical inference configuration JSON (+ the config itself) |
| `artifacts.output.sha256` | optional commitment over the inference output |
| `nonce` | 128-bit server-generated (or client-supplied, single-use) |
| `timestamp` | UTC ISO-8601 |
| `prev_hash` / `verification_hash` | hash chain: `verification_hash = SHA-256(canonical(payload ‖ prev_hash))` |
| `signature` | Ed25519 signature over the verification hash (site key, generated once at `TVP_SIGNING_KEY_PATH`) |

## Detection

- **Replay attack** — a presented record whose nonce is bound to a *different*
  record id fails verification (`replay_detected`); creating a record with an
  already-bound client nonce returns HTTP 409.
- **Record tampering** — recomputing the verification hash over the presented
  payload must reproduce the stored hash; any field edit breaks it
  (`hash_ok=false`, signature invalid).
- **Output substitution** — re-supplied artifact hashes
  (`input_sha256`, `model_sha256`, `config_sha256`, `output_sha256`) are
  compared against the committed values; mismatch ⇒ `artifacts_ok=false`.

## API

```bash
curl http://localhost:8200/health        # key id + public key

# create a record from server-side paths
curl -X POST http://localhost:8200/api/v1/provenance/records \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/data/img.jpg", "model_path": "/models/yolov8.pt",
       "config_path": "/configs/inference.json", "output_path": "/data/out.json"}'

# or upload the artifacts
curl -X POST http://localhost:8200/api/v1/provenance/records/upload \
  -F "image=@input.png" -F "model=@yolov8.pt" \
  -F 'config_json={"threshold": 0.5}' -F "output=@output.json"

# verify (idempotent by record_id, or against a presented record)
curl -X POST http://localhost:8200/api/v1/provenance/verify \
  -H "Content-Type: application/json" \
  -d '{"record_id": "tvp-…", "supplied_hashes": {"output_sha256": "…"}}'

# full ledger + integrity walk
curl http://localhost:8200/api/v1/provenance/chain
```

## Configuration (env, prefix `TVP_`)

| Variable | Default | Purpose |
|---|---|---|
| `TVP_WORKSPACE_DIR` | `workspace` | keys + ledger location |
| `TVP_SIGNING_KEY_PATH` | `<workspace>/keys/signing.pem` | Ed25519 private key (PKCS8 PEM) |
| `TVP_LEDGER_PATH` | `<workspace>/provenance/ledger.jsonl` | append-only ledger |
| `TVP_API_KEY` | – | enable API-key auth |

## Run

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn app.main:app --port 8200
```

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

Covers: record contents (all hashes/nonce/signature), chain linking +
integrity walk, stored-record verification, tampered-record rejection, replay
forgery, output substitution, and duplicate-nonce conflict.
