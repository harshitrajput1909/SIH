# TRUSTVISION — Enterprise Architecture

**AI Integrity Assurance Platform · Ministry of Defence deployment · Fully offline (air-gapped)**

Status: Design document · v1.0 · 19 Sep 2026

---

## 1. Overview & Architecture Principles

TRUSTVISION assures AI systems before and during operational use: it ingests
datasets and models, runs adversarial/integrity analysis, verifies inference
outputs with cryptographic provenance, records every action in a tamper-evident
audit trail, and produces signed assurance reports.

| # | Principle | Consequence |
|---|-----------|-------------|
| P1 | **Air-gapped by default** | No CDNs, no external model registries, no telemetry. All dependencies (npm, Maven, PyPI) and all ML models are vendored at build time. Fonts/assets are bundled locally. |
| P2 | **Separation of governance and compute** | Spring Boot owns state, RBAC, audit, reports. FastAPI owns heavy ML compute. The AI engine never touches the database. |
| P3 | **Modular monolith first** | One deployable Spring Boot JAR with hard module boundaries (Maven multi-module). Can be split into services later without domain changes. |
| P4 | **Everything is a job** | Every long-running analysis is a persisted, resumable, observable job with progress, heartbeats and an audit event per state change. |
| P5 | **Append-only accountability** | Every state change emits an audit event into a hash-chained, append-only ledger. UPDATE/DELETE is blocked at the database level. |
| P6 | **Cryptographic provenance everywhere** | SHA-256 checksums at ingest, signed verification nonces for inference, signed PDF reports. |
| P7 | **Offline identity** | Local accounts or site LDAP/Active Directory; internal PKI (CA) for TLS and report signing. No internet IdP. |

---

## 2. Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | React 19 + TypeScript + TailwindCSS v4 + Recharts + React Router | SPA served as static assets by the API container |
| Core backend | Java 21, Spring Boot 3 (Web, Security, Data JPA, Validation, SSE) | Governance plane: registry, RBAC, jobs, audit, reports |
| AI service | Python 3.12, FastAPI, Uvicorn, ONNX Runtime, PyTorch (CPU), OpenCV, NumPy/Pandas, Pillow, imagehash | Compute plane: parsing, scanning, verification |
| Database | PostgreSQL 16+ | All relational state (one instance, schema-per-module) |
| Artefact store | Local filesystem volume or MinIO (S3 API, self-hosted) | Dataset/model/image/report binaries |
| Identity | Local accounts or site LDAP/AD; internal CA (mTLS + TLS) | Offline authentication |
| Packaging | Docker images + docker-compose (single-node) / optional Helm | Offline installation bundles |

**Runtime services:** `frontend` (static, served by API), `tv-api` (Spring Boot),
`tv-ai` (FastAPI), `postgres`, optional `minio`.

---

## 3. System Context

```
┌────────────────────────────── OFFLINE DEPLOYMENT (air-gapped site) ──────────────────────────────┐
│                                                                                                   │
│   ┌────────────────────┐                                                                          │
│   │ Browser (React SPA)│  analyst / auditor / admin                                               │
│   └─────────┬──────────┘                                                                          │
│             │ HTTPS  ·  REST (JSON)  +  SSE (job progress)                                        │
│             ▼                                                                                     │
│   ┌─────────────────────────────┐        mTLS REST + shared artefact volume        ┌────────────┐ │
│   │  tv-api  (Spring Boot 3)    │◄───────────────────────────────────────────────►│ tv-ai       │ │
│   │  governance & orchestration │        submit job / progress / final result      │ (FastAPI)   │ │
│   └──────┬───────────────┬──────┘                                                  └──────┬──────┘ │
│          │ JDBC          │ storage SDK / volume path                                      │        │
│          ▼               ▼                                                                ▼        │
│   ┌────────────┐   ┌──────────────────────────────┐   ┌─────────────────────────────────────┐    │
│   │ PostgreSQL │   │ Artefact Store (FS / MinIO)  │◄──│ local model store (embedded ONNX/   │    │
│   │ 6 schemas  │   │ datasets · models · reports  │   │ weights used by the engine itself)  │    │
│   └────────────┘   └──────────────────────────────┘   └─────────────────────────────────────┘    │
│                                                                                                   │
│   ✗ no internet egress   ✗ no external IdP   ✗ no CDN   ✓ internal CA, LDAP/AD optional          │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Service Architecture

### 4.1 Frontend — React SPA

- Served by `tv-api` as static assets (single origin → no CORS in production).
- Feature-sliced: one folder per assurance module; shared UI kit (Card, Chip,
  Gauge, Button…); typed API contracts mirror the backend DTOs.
- Talks **only** to `tv-api`. Never to the AI engine or the database.
- Long jobs tracked via **SSE** (`GET /api/v1/jobs/{id}/events`) with polling
  fallback — both work behind an air gap.

### 4.2 Core Backend — Spring Boot 3 / Java 21 (modular monolith)

Single bootable JAR (`tv-platform`) composed of hard-boundary Maven modules:

| Module | Responsibility |
|--------|----------------|
| `tv-shared` | Kernel: security filters, error model, event bus (transactional outbox), storage abstraction, JSON canonicalisation |
| `tv-identity` | Users, roles, clearances, RBAC, service accounts (AI engine client auth) |
| `tv-dataset` | Dataset & version registry, COCO/YOLO ingest orchestration, quality findings, contributor risk, anomalies, evidence, dataset trust score |
| `tv-model` | Model & version registry (ONNX/PyTorch/TorchScript), scan orchestration, risk findings, access-mode scans, training-source risk, model trust score |
| `tv-inference` | Verification requests, nonce/HMAC issue & replay checks, provenance records, integrity results |
| `tv-jobs` | Analysis job lifecycle, AI engine client (submit / progress / result), SSE fan-out, retries & timeouts |
| `tv-audit` | Consumes domain events → append-only hash-chained ledger; audit query API; ledger verification job |
| `tv-reports` | Report templates, PDF/CSV assembly (Apache PDFBox — offline), internal-CA signing, report registry |
| `tv-platform` | Composition root: configuration, module wiring, OpenAPI, static frontend hosting |

Rules enforced by architecture tests (ArchUnit): `tv-dataset` may not depend on
`tv-model` etc. — cross-module interaction only through `tv-shared` contracts.

### 4.3 AI Engine — Python FastAPI (compute plane)

Stateless workers behind a small REST surface. Pulls artefacts from the shared
store; never queries PostgreSQL; authenticates to `tv-api` with a service
account (mTLS + API key).

| Capability group | Supports / techniques |
|---|---|
| **Dataset parsing** | **COCO** (`images/annotations/categories` JSON), **YOLO** (per-image `.txt` + `data.yaml`), format auto-detection, class taxonomy mapping |
| **Dataset quality** | Perceptual-hash (pHash/dHash) duplicate clustering, corrupt/decode scan, missing-label detection, statistical outlier screens |
| **Distribution drift** | PSI / KS per feature group, class-share drift vs certified baseline, domain slicing (day/night/urban/…) |
| **Dataset anomalies** | Label-flip detection (model-consensus vs ground truth), cross-contributor duplicate clusters, backdoor trigger heuristics (patch–prediction correlation), OOD detection (embedding confidence manifolds using locally vendored models) |
| **Model scanning** | **ONNX**: onnx checker, opset/op allowlist audit, graph sanity, runtime probes via ONNX Runtime · **PyTorch** `.pt/.pth`: safe loading (`weights_only`, prefer safetensors; pickle-risk flagging), weight statistics, module inventory · **TorchScript**: `torch.jit` graph load + op allowlist · backdoor / adversarial / drift / confidence risk probes |
| **Inference verification** | Reproduce prediction (ONNX Runtime / torch CPU), confidence scoring, image-tamper & adversarial-noise detectors, manipulation risk scoring, input SHA-256 / model digest / config hash computation, replay validation support |

Long tasks run in a bounded worker pool; each job reports accepted → progress
(0–100) → completed/failed via callbacks to `tv-api`.

### 4.4 Data & Storage

- **PostgreSQL** — the only system of record (schemas: `identity`, `dataset`,
  `model`, `inference`, `audit`, `report`, `job`). See §6.
- **Artefact store** — versioned paths:
  `datasets/{datasetId}/{version}/…`, `models/{modelId}/{version}/…`,
  `inference/{requestId}/…`, `reports/{reportId}/…`.
  DB stores logical refs + SHA-256; never binaries.
- **Local model store (AI engine)** — engine-owned embedded models
  (embedding/OOD backbones, detectors), shipped inside the image.

### 4.5 Deployment Topology (offline site)

- **Single node (default):** docker-compose with 4 containers
  (`tv-api`, `tv-ai`, `postgres`, `minio` or host volumes). Volumes for DB data
  and artefacts. Images delivered on removable media with an offline install bundle.
- **Multi-node (optional):** Kubernetes/Helm — `tv-api` ×2 behind site LB,
  `tv-ai` scaled horizontally as workers, Postgres with streaming replica,
  shared RWX volume (or MinIO) for artefacts.
- TLS everywhere via internal CA; mTLS between `tv-api` and `tv-ai`;
  deny-all egress firewall rules on all containers.

---

## 5. Folder Structure (monorepo)

```
trustvision/
├── frontend/                        # React + TS + Tailwind SPA (current app, moved here)
│   ├── public/
│   ├── src/
│   │   ├── app/                     # router, providers, layout shell
│   │   ├── components/              # shared UI kit (Card, Chip, Gauge, Button…)
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── datasets/            # pages, components, hooks, api.ts
│   │   │   ├── models/
│   │   │   ├── inference/
│   │   │   ├── audit/
│   │   │   └── reports/
│   │   ├── lib/                     # api client, SSE hook, formatters
│   │   ├── types/                   # DTO contracts (mirror backend)
│   │   └── styles/
│   ├── package.json                 # deps vendored for offline build
│   └── vite.config.ts
│
├── backend/                         # Spring Boot 3 · Java 21 · multi-module Maven
│   ├── pom.xml                      # parent BOM
│   ├── tv-platform/                 # bootable composition root (serves frontend too)
│   ├── tv-shared/                   # kernel: security, outbox events, storage, errors
│   ├── tv-identity/                 # users · roles · RBAC · service accounts
│   ├── tv-dataset/                  # dataset assurance module
│   ├── tv-model/                    # model assurance module
│   ├── tv-inference/                # inference assurance module
│   ├── tv-jobs/                     # job orchestration + AI engine client + SSE
│   ├── tv-audit/                    # append-only hash-chained audit ledger
│   └── tv-reports/                  # PDF/CSV report generation + signing
│
├── ai-engine/                       # Python 3.12 · FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                     # routers: health, jobs (submit/progress/result)
│   │   ├── core/                    # settings, auth (mTLS/API key), logging
│   │   ├── domain/                  # job & finding result models
│   │   ├── services/
│   │   │   ├── datasets/            # coco.py · yolo.py · dedup.py · quality.py · drift.py · ood.py
│   │   │   ├── models/              # onnx_inspector.py · pytorch_inspector.py · torchscript_inspector.py
│   │   │   ├── inference/           # verifier.py · integrity.py · provenance.py
│   │   │   └── support/             # artefact fetch, metrics serialization
│   │   ├── workers/                 # worker pool, heartbeats, callbacks
│   │   └── models/                  # vendored engine models (offline)
│   ├── tests/
│   └── pyproject.toml
│
├── deploy/
│   ├── docker/                      # Dockerfiles (frontend→api bundle, ai-engine, postgres)
│   ├── compose/                     # docker-compose.yml for single-node offline site
│   ├── helm/                        # optional Kubernetes charts
│   └── config/                      # internal CA certs, env profiles, RBAC seeds
│
└── docs/
    └── ARCHITECTURE.md              # this document
```

> Migration note: the existing SPA currently lives at the repo root; move it to
> `frontend/` and adopt the feature-sliced layout above. Backend, AI engine and
> deploy folders are new.

---

## 6. Database Architecture (PostgreSQL)

One instance, **one schema (namespace) per bounded context**. Applications
connect with a role that may write only its own schema; `audit` is
insert-only (UPDATE/DELETE revoked and trigger-blocked).

### 6.1 Schema overview

```
identity.users ──┐
                 │ owns / acts on
                 ▼
dataset.datasets ─1─< dataset.dataset_versions ─1─< dataset.quality_findings
                                       │             dataset.contributor_risks
                                       │             dataset.anomalies ─1─< dataset.evidence
                                       └─────1────────dataset.assessments
model.models ─1─< model.model_versions ─1─< model.risk_findings
                                       ├─< model.access_scans
                                       ├─< model.training_sources
                                       └───1─model.assessments
inference.requests ─1─ inference.results ─1─< inference.integrity_checks
job.analysis_jobs (polymorphic ref: dataset version | model version | inference request)
report.reports (refs any assessment / audit export)
audit.events  ◄── fed by transactional outbox from every module (insert-only, hash chain)
```

### 6.2 Table catalogue

**identity**
| Table | Key columns |
|---|---|
| `users` | id, username, full_name, role, clearance, auth_source (LOCAL/LDAP), status |
| `service_accounts` | id, name, key_hash, scopes, enabled — used by `tv-ai` |

**dataset** — supports COCO & YOLO
| Table | Key columns |
|---|---|
| `datasets` | id, name, codename, classification, owner_id, status |
| `dataset_versions` | id, dataset_id, version, format (`COCO`/`YOLO`), artefact_ref, sha256, size_bytes, stats jsonb (image count, classes, formats), uploaded_by, uploaded_at, state |
| `quality_findings` | id, version_id, type (`DUPLICATE`/`CORRUPTED`/`MISSING_LABEL`/`SUSPICIOUS`), count, percent, severity, details jsonb |
| `contributor_risks` | id, version_id, name, unit, samples, risk_score, risk_level |
| `anomalies` | id, version_id, type (`LABEL_FLIP`/`DUPLICATE_CLUSTER`/`BACKDOOR_TRIGGER`/`OOD`), count, severity, status |
| `evidence` | id, version_id, anomaly_id?, image_ref, true_label, predicted_label, risk_level, reason, confidence |
| `assessments` | id, version_id, trust_score, risk_level, component_scores jsonb, recommended_actions jsonb, assessed_at |

**model** — supports ONNX / PyTorch / TorchScript
| Table | Key columns |
|---|---|
| `models` | id, name, framework (`ONNX`/`PYTORCH`/`TORCHSCRIPT`), task, owner_id |
| `model_versions` | id, model_id, version, artefact_ref, sha256, size_bytes, params, input_size, architecture, state |
| `risk_findings` | id, version_id, type (`BACKDOOR`/`ADVERSARIAL`/`PREDICTION_DRIFT`/`CONFIDENCE_DRIFT`), severity, score, details jsonb |
| `access_scans` | id, version_id, access_mode (`WHITE_BOX`/`BLACK_BOX`), verdict, notes |
| `training_sources` | id, version_id, source (`CORE`/`FINE_TUNED`/`EXTERNAL_WEIGHTS`/`AUGMENTED`), risk_level |
| `assessments` | id, version_id, trust_score, risk_level, … |

**inference**
| Table | Key columns |
|---|---|
| `requests` | id, image_ref, image_sha256, model_version_id, nonce, hmac, requested_by, requested_at |
| `results` | id, request_id, predicted_label, confidence, model_digest, config_hash, signature_status, replay_check, executed_at |
| `integrity_checks` | id, result_id, type (`TAMPERING`/`ADVERSARIAL_NOISE`/`MANIPULATION`/`REPLAY`), verdict, score |

**audit** (append-only, monthly range partitions)
| Table | Key columns |
|---|---|
| `events` | id (bigserial), occurred_at, actor_id, actor_name, module, action, target_type, target_id, outcome, details jsonb, prev_hash, entry_hash |

**report**
| Table | Key columns |
|---|---|
| `reports` | id, type (`ASSESSMENT`/`AUDIT_EXPORT`/`COMPLIANCE`), subject_type, subject_id, format, artefact_ref, sha256, signature, generated_by, generated_at |
| `templates` | id, code, version, layout_ref |

**job**
| Table | Key columns |
|---|---|
| `analysis_jobs` | id, type (`DATASET_SCAN`/`MODEL_SCAN`/`INFERENCE_VERIFY`), subject_ref, status, progress, attempts, payload jsonb, result_ref, ai_job_id, error, submitted_by, queued_at, started_at, finished_at |
| `outbox_events` | id, aggregate_type, aggregate_id, event_type, payload jsonb, created_at, published_at — transactional outbox feeding `audit` + SSE |

### 6.3 Conventions & integrity

- **Keys:** UUIDv7 (time-ordered) app-generated; audit uses bigserial.
- **Audit hash chain:** `entry_hash = SHA-256(prev_hash ‖ canonical_json(event))`;
  INSERT-only role + BEFORE UPDATE/DELETE triggers raise exceptions; nightly
  verification job re-walks the chain and raises on tampering.
- **Outbox pattern:** domain events are written in the same transaction as the
  state change; a dispatcher feeds the audit ledger and SSE stream.
- **jsonb** for flexible finding payloads; hot-filtered fields are real columns;
  GIN indexes on jsonb where queried.
- **Indexes:** findings/evidence by `version_id`; jobs by (`status`, `queued_at`);
  audit by `occurred_at`, `actor_id`, `(module, action)`.
- **Migrations:** Flyway, one V-prefix path per module (`V100__dataset/...`,
  `V200__model/...`) so modules never edit each other's DDL.
- **Retention:** artefacts per site policy; audit partitions retained
  indefinitely (exported annually to WORM storage).

---

## 7. Communication Flow

### 7.1 Security & session flow

```
Browser ──HTTPS(TLS, internal CA)──► tv-api
  login → session cookie (HttpOnly, signed JWT, 30 min, sliding)
  RBAC: ADMIN > AUDITOR > ANALYST > VIEWER, per-module permission matrix
tv-api ──mTLS + service-account key──► tv-ai        (both containers: egress deny-all)
tv-ai ──artefact reads/writes──► shared store volume (paths issued by tv-api per job)
```

### 7.2 Job lifecycle (all analyses)

```
            ┌─────────┐   submit    ┌─────────┐  heartbeat/progress  ┌───────────┐
QUEUED ────►│ ACCEPTED│────────────►│ RUNNING │─────────────────────►│ COMPLETED │
 (tv-api)   └─────────┘             └────┬────┘                      └───────────┘
      ▲                                  │ timeout / crash / error          │
      └────────── retry (max 2) ◄────────┴──────────────────────►│ FAILED ◄──┘
```

- `tv-api` persists the job first (audit event `JOB_QUEUED`), then submits to
  `tv-ai`. Progress rows/SSE updates are emitted from worker heartbeats.
- A reaper fails jobs with stale heartbeats and retries idempotently
  (AI engine work is keyed by job id; results are posted once).

### 7.3 Dataset assurance flow (upload → score → report)

```
Analyst        Frontend            tv-api                      tv-ai                Store
   │  upload zip  │                   │                           │                    │
   ├─────────────►│  POST /datasets/{id}/versions (multipart)     │                    │
   │              ├──────────────────►│ validate format (COCO/YOLO)│                   │
   │              │                   │ sha256 → store artefact    │                   │
   │              │                   │ INSERT version + job ──────┼──► POST /jobs ───►│
   │              │◄─ 202 {versionId, jobId} ────────────┤          │ fetch artefact    │
   │              │                   │                    pipeline: parse COCO/YOLO    │
   │              │                   │                    → dedup → quality → drift    │
   │              │                   │◄── PATCH progress 20…90% ──┤  → anomalies → evidence
   │              │◄══ SSE progress ══│                            │                   │
   │              │                   │◄── POST /jobs/{id}/result ─┘                   │
   │              │                   │ persist findings, evidence, trust score         │
   │              │                   │ audit: SCAN_COMPLETED, SCORE_ISSUED             │
   │  review UI   │  GET /datasets/{id}/versions/{v}/findings         │                   │
   ├─────────────►│──────────────────►│                                                 │
   │  report      │  POST /reports {subject: dataset-version}          │                   │
   ├─────────────►│──────────────────►│ PDFBox assemble + CA-sign → store → audit       │
   │              │◄─ report ref (download)                                            │
```

### 7.4 Model assurance flow

Same job pattern; the artefact is an `.onnx` / `.pt` / `.torchscript` file.
`tv-ai` dispatches per framework:

```
ONNX        → onnx checker + op-allowlist audit → ONNX Runtime probes
PyTorch     → safe weight load (weights_only/safetensors; pickle risk flagged)
              → weight stats → module inventory → probes
TorchScript → torch.jit graph load + op allowlist → probes
probes      → backdoor heuristics · adversarial robustness · prediction/confidence drift
result      → risk findings + access verdict (white/black box) + training-source risk
              → model trust score (tv-api) → audit → report
```

### 7.5 Inference verification flow

```
Analyst        Frontend            tv-api                       tv-ai
   │  submit img ├──────────────────►│ compute input SHA-256, nonce + HMAC        │
   │             │                   │ store image, INSERT request + job ──► tv-ai │
   │             │                   │                    load registered model    │
   │             │                   │                    (ONNX Runtime / torch)   │
   │             │                   │                    predict → confidence     │
   │             │                   │                    integrity detectors      │
   │             │                   │                    digests: model/config    │
   │             │                   │◄── result {label, conf, integrity, digests} │
   │             │                   │ verify HMAC/replay (nonce single-use)       │
   │             │                   │ persist result + integrity checks           │
   │             │                   │ audit: INFERENCE_VERIFIED / FLAGGED         │
   │             │◄─ verdict card (Trusted 88% / Flag For Review) ──┤
```

### 7.6 Progress streaming

`tv-api` exposes `GET /api/v1/jobs/{id}/events` (SSE). Events originate from the
transactional outbox (`JOB_QUEUED`, `JOB_PROGRESS`, `JOB_COMPLETED`,
`JOB_FAILED`, `ASSESSMENT_ISSUED`). The frontend subscribes while the job view
is open and falls back to 2 s polling if SSE is unavailable.

### 7.7 Interface surface (summary)

| Module | Representative endpoints (tv-api) |
|---|---|
| Identity | `POST /auth/login`, `GET /users`, `POST /users`, `GET /me` |
| Datasets | `GET/POST /datasets`, `POST /datasets/{id}/versions`, `GET …/findings`, `GET …/evidence`, `GET …/assessment` |
| Models | `GET/POST /models`, `POST /models/{id}/versions`, `GET …/findings`, `GET …/assessment` |
| Inference | `POST /inference/verify` (multipart), `GET /inference/requests/{id}`, `GET …/result` |
| Jobs | `GET /jobs/{id}`, `GET /jobs/{id}/events` (SSE) |
| Audit | `GET /audit/events` (filtered), `GET /audit/verify` |
| Reports | `POST /reports`, `GET /reports/{id}/download` |
| AI engine (internal) | `POST /jobs`, `PATCH /jobs/{id}/progress`, `POST /jobs/{id}/result`, `GET /health` |

---

## 8. Offline Assurance Checklist

- Build-time vendoring: npm cache, Maven repo mirror, PyPI wheelhouse committed
  to the install bundle; images built on a connected build host, shipped as tarballs.
- Frontend fonts/icons bundled locally (no Google Fonts link in `index.html`).
- AI engine models (OOD backbones etc.) shipped inside the image; no HuggingFace
  downloads at runtime.
- ONNX Runtime / PyTorch CPU wheels included; no GPU/CUDA dependency required.
- Identity: local accounts or site LDAP/AD; internal CA certificates distributed
  with the install bundle; report signing key held in site HSM/secret store.
- Time sync from site NTP; audit chain verification scheduled job.
- No telemetry, no auto-update channels; versioned offline upgrade runbooks.

---

## 9. UI → Architecture Mapping

| Screen (implemented SPA) | Backing module | Primary endpoints |
|---|---|---|
| Dashboard tiles + recent assessments | cross-module read API | `GET /overview/summary` |
| Dataset header card (file, status, upload) | tv-dataset | `POST /datasets/{id}/versions` |
| Data Quality gauges | tv-dataset ← AI findings | `GET …/quality-findings` |
| Distribution tabs (feature/class/domain) | tv-dataset ← AI drift results | `GET …/drift?dim=feature|class|domain` |
| Contributor Risk | tv-dataset | `GET …/contributors` |
| Anomaly Assessment + Evidence | tv-dataset | `GET …/anomalies`, `GET …/evidence` |
| Assurance Summary + Quarantine | tv-dataset | `GET/POST …/assessment`, `POST …/quarantine` |
| Model page (overview, risks, access mode) | tv-model | `GET /models/{id}/versions/{v}` |
| Inference page (provenance, integrity) | tv-inference | `POST /inference/verify`, `GET …/result` |
| Audit & Reports table | tv-audit, tv-reports | `GET /audit/events`, `POST /reports` |
