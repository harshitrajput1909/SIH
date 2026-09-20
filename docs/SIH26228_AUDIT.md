# SIH26228 Compliance Audit — TRUSTVISION

Auditor role: Senior Solution Architect / Cybersecurity Auditor / AI Assurance Expert / SIH Grand Finale Evaluator
Date: 19 Sep 2026 · Scope: all code, schemas, APIs, UI and docs in `trustvision/`
Method: evidence-based — every status below was verified against the repository (file-level grep + test runs), not against intent.

Verified evidence base at audit time:
- `ai-engine/` — Dataset Assurance Engine (FastAPI), 7 detectors, tests **4/4 PASS**
- `model-engine/` — Model Integrity Engine (FastAPI), white/black-box, tests **7/7 PASS**
- `provenance-engine/` — Provenance Engine (FastAPI), hash chain + Ed25519, tests **9/9 PASS**
- `backend/` — Spring Boot 3.4 / Java 21, **Dataset module only**, builds to jar (`BUILD OK`)
- `frontend/` (repo root) — React/TS/Tailwind UI, 5 pages, **fully mock-driven (no API calls)**
- `docs/` — ARCHITECTURE.md, DATABASE.md, db/schema.sql (13-table design)

---

## 1. Training Data Integrity

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Duplicate Detection | ✅ | `ai-engine/app/services/detectors/duplicates.py` — SHA-256 exact + two-stage pHash (8-band candidates → Hamming → pixel MAD confirmation). Tested. |
| Near-Duplicate Flooding Detection | ✅ | `detectors/flooding.py` — cluster size + ≥80% class/contributor coherence. Tested. |
| Label Flip Detection | ✅ | `detectors/label_flip.py` — stratified K-fold out-of-fold consensus vs given label + conflicting-label duplicate groups. Tested. |
| Systematic Mislabeling Detection | ✅ | `detectors/systematic_mislabel.py` — contributor-conditional confusion, one-proportion z-test vs leave-self-out background. Tested. |
| Trigger Injection Detection | ⚠️ | `detectors/trigger_injection.py` — single heuristic family: 4×4 grid patch recurrence (pHash + uniformity + colour key) + class-rarity filter. **Not covered:** invisible/adversarial triggers, dynamic triggers, non-patch semantics, trigger reverse-engineering (no Neural-Cleanse-style inversion), no benchmark validation. |
| Out-of-Distribution Detection | ✅ | `detectors/ood.py` — IsolationForest + nearest-class Mahalanobis (Ledoit-Wolf) on OOF consensus embeddings. Thresholds documented. |
| Contributor Risk Aggregation | ✅ | `detectors/contributor_risk.py` — probabilistic-AND blend of per-detector rates → 0–100 score, level, flagged, confidence. Tested. |

Section score: **6.6 / 7**

## 2. Model Integrity

| Requirement | Status | Evidence / Gap |
|---|---|---|
| White-Box Assessment | ✅ | `model-engine/app/services/checks/whitebox.py` — parameter stats, layer analysis, activation hooks (full modules only). Tested. |
| Black-Box Assessment | ✅ | `checks/blackbox.py` — oracle-only battery mode. Tested on ONNX. |
| Behavioural Fingerprinting | ✅ | `blackbox.behavioural_fingerprint` — deterministic probe set → per-output stats + signature digest. |
| Model Fingerprinting | ✅ | `services/fingerprints.py` — FILE_SHA256, canonical WEIGHT_SHA256, ONNX_GRAPH_HASH / TORCHSCRIPT_CODE_HASH. Tested. |
| Backdoor Detection | ⚠️ | `blackbox.backdoor_scan` — perturbation flip-rate × concentration (patch + feature-toggle). **Not covered:** white-box trigger localisation in weights, trigger inversion, invisible triggers; validated only on a synthetic gate model. |
| Model Substitution Detection | ✅ | Fingerprints + behavioural divergence vs reference → 4-state verdict. Tested both paths. Requires a reference artefact (limitation is stated when absent). |
| Confidence Scoring | ✅ | Coverage-weighted confidence in every result. |
| Limitation Reporting | ✅ | Per-run `limitations` list assembled from every skipped check and assumption. Tested. |

Section score: **7.45 / 8**

## 3. Inference Provenance & Output Integrity

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Input SHA256 | ✅ | `provenance-engine/app/services/provenance.py` → `artifacts.input.sha256`. Tested. |
| Model Digest | ✅ | `artifacts.model.sha256`. Tested. |
| Configuration Hash | ✅ | Canonical-JSON SHA-256 of the config + content embedded. Tested. |
| Nonce | ✅ | 128-bit server nonce; client nonces single-use (HTTP 409 on reuse). Tested. |
| Timestamp | ✅ | UTC ISO-8601 on every record. |
| Digital Signature | ✅ | Ed25519 over the verification hash; offline PKCS8 key store; key id + public key exposed on `/health`. |
| Replay Attack Detection | ✅ | Nonce registry: presented record bound to a different record id ⇒ `replay_detected`. Creation-time 409. Tested. |
| Tampering Detection | ✅ | `verification_hash` recomputation over the presented payload. Tested. |

Also: output-substitution detection (`supplied_hashes` vs commitments) and a full chain-integrity walk (`GET /chain`) — both tested.
Section score: **7.6 / 8** (deduction: none of this is persisted by the Spring backend or surfaced by the UI — see Missing Components M4/M8).

## 4. Distribution Shift & Anomaly Assessment

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Feature Drift | ❌ | **No drift code exists in the AI engine** (verified: grep for PSI/KL/drift across `ai-engine/app/` returns nothing). The frontend "Feature Drift" chart is rendered from mock JSON (`src/data/dataset.json`), not engine output. |
| Class Drift | ❌ | Same — mock chart only. |
| Domain Drift | ❌ | Same — mock chart only. |
| Terrain Shift | ❌ | No metadata/EXIF ingestion anywhere; slicing impossible without capture metadata. |
| Season Shift | ❌ | Not implemented; no timestamp/EXIF pipeline. |
| Sensor Shift | ❌ | Not implemented; no sensor/device metadata model. |
| Illumination Shift | ❌ | Not implemented (no EXIF/brightness-histogram slicing). |

Section score: **0.5 / 7** (cosmetic mock charts earn nothing; OOD is credited under §1). **This is the largest non-compliance in the solution.**

## 5. Analyst Facing Assurance

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Human Readable Evidence | ⚠️ | Engines emit structured evidence; backend persists and serves it (`GET /dataset/evidence/{id}`); **UI evidence preview is mock data**, not API-bound. |
| Severity Score | ✅ | Engine findings carry severity; backend persists; UI renders badges (mock-bound). |
| Confidence Score | ✅ | Engine + backend per finding/per analysis. |
| Recommended Action | ⚠️ | UI shows recommended actions from mock JSON; **neither engine generates recommended actions**; backend has no field for them. |
| Accept / Review / Quarantine | ⚠️ | UI buttons exist but are inert by design; backend has **no quarantine/review/accept endpoints** (verified: grep — none) although the DB state (`QUARANTINED`, `quarantined_at`) exists. |

Section score: **3.5 / 5**

## 6. Audit Requirements

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Tamper-Evident Audit Trail | ⚠️ | Provenance ledger is tamper-evident for inference records; the **Spring backend emits no audit events** and its `audit_logs` table (designed in docs/schema.sql) is absent from Flyway V1. |
| Hash Chaining | ✅ | `provenance-engine/services/ledger.py` — prev_hash/verification_hash chain over canonical JSON, append-only file. Tested. |
| Event Verification | ⚠️ | `POST /verify` + `GET /chain` re-walk hashes/signatures. Tested. No scheduled/periodic verification job; no backend-action audit to verify. |

Section score: **2.0 / 3**

## 7. Coverage Statement

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Supported Attack Classes | ⚠️ | Capability tables exist in engine READMEs; no consolidated, versioned coverage statement artifact or `/coverage` API. |
| Unsupported Attack Classes | ❌ | Nowhere enumerated (e.g., invisible triggers, GAN-forged samples, distributed steganographic triggers, multi-frame exploits). |
| Assumptions | ⚠️ | Scattered across docs (architecture §1, READMEs); not consolidated. |
| Limitations | ⚠️ | Per-run limitations genuinely generated by both engines (tested); no consolidated statement; UI does not render engine limitations (mock only). |

Section score: **1.75 / 4**

## 8. Technical Constraints

| Requirement | Status | Evidence / Gap |
|---|---|---|
| Offline Operation | ⚠️ | Engines: fully offline (no downloads, HF guards, vendored models). **Frontend violates it**: `index.html:13-16` loads Public Sans from `fonts.googleapis.com`. |
| Air-Gapped Compatibility | ⚠️ | Engines are dependency-pinnable and wheel-installable; **no Dockerfiles, no docker-compose, no offline bundle script exist** (architecture §4.5 is design only). |
| COCO Support | ✅ | `ingestion.load_coco` implemented incl. auto-detection; note: not covered by an automated test. |
| YOLO Support | ✅ | `ingestion.load_yolo` + data.yaml/classes.txt parsing. Tested end-to-end. |
| ONNX Support | ✅ | Model engine: load, stats, layer analysis, execution. Tested (IR-version caveat handled). |
| PyTorch Support | ✅ | state_dict + gated full-module loading. Tested. |
| TorchScript Support | ✅ | `torch.jit.load`, code-hash, execution. Tested. |

Section score: **6.1 / 7**

---

## Scores

| Score | Value | Basis |
|---|---|---|
| **Compliance Score** | **72 / 100** | 35.5 of 49 requirement items fully/partially satisfied (§4 is the collapse point). |
| **Architecture Score** | **76 / 100** | Strong 3-service separation, tested engines, sound schema design; deductions: only 1 of 4 backend modules built, engines not orchestrated by the backend, monorepo layout not adopted, in-memory job stores vs designed orchestration, no deployment topology in code. |
| **Security Score** | **66 / 100** | Good: Ed25519 + hash chains + SHA-256 discipline, append-only ledger, zip-slip guard, pickle execution gate, offline-by-default. Missing: **no authentication/authorization on any API** (no Spring Security dependency), plaintext PEM key on disk, no TLS config, no rate limiting, no backend audit logging, engine endpoints unauthenticated by default. |
| **SIH Readiness Score** | **64 / 100** | Dataset-assurance story is demonstrable; model/provenance engines are standalone demos; UI is not wired to any backend; no one-command deployment; two headline PS requirements (distribution shifts, integrated model assurance) incomplete. |

---

## Missing Components List

| ID | Component | Exact location to add | Required changes |
|----|-----------|----------------------|------------------|
| M1 | Feature/Class drift detectors (PSI, KL) | `ai-engine/app/services/detectors/drift.py`; stage in `services/pipeline.py`; schema entries in `app/schemas.py` | Engine: compute PSI/KS per feature, class-share deltas vs certified baseline |
| M2 | Metadata slicing (terrain/season/sensor/illumination) | `ai-engine/app/services/ingestion.py` (EXIF/metadata parse), `detectors/drift.py` (slicing), `dataset.json`→API | Ingest capture metadata; slice OOD/drift by domain; emit `domain_drift` |
| M3 | Model Assurance Spring module | `backend/.../domain|repo|service|controller` (new `model/` packages); `AiEngineClient` extension to model-engine `POST /api/v1/assessments` | Upload/analyze/get/report endpoints mirroring dataset module |
| M4 | Provenance Spring module | `backend/...` new `inference/` packages proxying provenance-engine + persistence | Store records/verifications; expose `/inference/verify`, `/inference/records` |
| M5 | Quarantine / Review / Accept actions | `DatasetController` + `DatasetService` (`POST /dataset/{id}/quarantine`, `/review`, `/accept`); state transition guard | UI buttons call APIs; audit events emitted |
| M6 | Backend audit trail | `V2__audit.sql` (audit_logs, hash-chained per docs/schema.sql); `AuditService`; emit on every state change; verification job | — |
| M7 | Authentication & RBAC | `spring-boot-starter-security`, JWT/session or LDAP; roles ADMIN/AUDITOR/ANALYST/VIEWER; protect all endpoints; enforce engine API keys | — |
| M8 | Frontend ↔ backend wiring | `src/lib/api.ts` (new), replace `src/data/*.json` imports in `DatasetAssurancePage`, `DashboardPage`, etc.; SSE/polling for jobs | All 5 pages live; evidence images served |
| M9 | Deployment artifacts | `deploy/docker/` (3 Dockerfiles), `deploy/compose/docker-compose.yml`, offline wheel/npm bundle script; **remove Google Fonts from `index.html:13-16`** (bundle Public Sans) | — |
| M10 | Coverage statement | `docs/COVERAGE.md` + `GET /coverage` on all engines (auto-derived from capability registry: supported/unsupported attack classes, assumptions, limitations) | — |
| M11 | Recommended-action generation | Dataset/model engines: emit `recommended_actions[]` per trust level and finding; persist in `dataset_analysis`/report payload | — |
| M12 | PDF report rendering | Backend reports module: PDFBox render of the report payload (currently JSON artefact only) | — |
| M13 | COCO ingestion test | `ai-engine/tests` — COCO fixture alongside the YOLO one | — |
| M14 | Monorepo migration | Move frontend to `frontend/` per ARCHITECTURE.md §5 | — |

## Priority Fix List

| Priority | Fix | Why it blocks SIH |
|----------|-----|-------------------|
| **P0** | M8 — wire the frontend to the backend (dataset flow end-to-end) | A Grand Finale demo with 100% mock screens is the first thing evaluators probe |
| **P0** | M1/M2 — drift detection + metadata slicing | Feature/Class/Domain/Terrain/Season/Sensor/Illumination drift is 7 explicit PS items; currently 0% engine coverage |
| **P0** | M9 — docker-compose + local fonts | "Offline/air-gapped" is a scored constraint; a Google-Fonts request and manual setup contradict it |
| **P1** | M5 — quarantine/review/accept endpoints + wiring | Analyst decision loop is in the PS and currently dead-ends in inert buttons |
| **P1** | M3/M4 — model + provenance Spring modules | Turns two standalone demos into the integrated platform the PS demands |
| **P1** | M6 — backend audit trail | "Tamper-evident audit trail" must span the platform, not only the provenance ledger |
| **P1** | M10 — coverage statement | Explicit PS deliverable ("Limitation Statement"); cheapest high-value item |
| **P2** | M7 — auth/RBAC · M11 — recommended actions · M12 — PDF · M13 — COCO test · M14 — monorepo | Hardening and completeness |

## Final Verdict

TRUSTVISION is **a technically genuine, well-tested prototype with professional documentation — but it is not yet an integrated platform, and an SIH Grand Finale evaluator will notice within minutes.**

What is genuinely strong and rare at this stage: three real assurance engines (not slideware) with green test suites; honest, machine-generated limitation statements; a correctly implemented Ed25519-signed, hash-chained provenance ledger; two-stage near-duplicate detection with pixel-level verification; and concentration-gated backdoor probing. The data-integrity section (§1) is near-complete and the provenance section (§3) is complete at the engine level.

What fails strict review: **Requirement 4 (distribution shifts) has zero engine implementation** — the UI charts are decorative mock data; **Requirements 2 and 3 are engine-only** — the Spring backend implements just one of four modules, so model and provenance results are never persisted, never authenticated, and never shown in the (fully mock-driven) UI; there are **no analyst decision endpoints** (quarantine/review/accept), **no backend audit trail**, **no authentication**, and **no deployment artifacts** — while the frontend quietly makes a Google-Fonts request that breaks the air-gap claim.

**Verdict: CONDITIONAL PASS — 72/100 compliance.** With the P0 sprint (live dataset flow, drift detection, deployment bundle) and the P1 integration sprint (model/provenance modules, audit, quarantine, coverage statement), this becomes a legitimate top-tier SIH solution. Without them, it remains three excellent engines beside a beautiful mock.

— End of audit.
