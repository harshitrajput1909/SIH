# TRUSTVISION — SIH26228 Gap-Fix Roadmap

Derived from `docs/SIH26228_AUDIT.md` (Compliance 72 · Architecture 76 · Security 66 · SIH Readiness 64).
Fixes are ranked by impact on the SIH26228 evaluation scores. Effort is in ideal dev-days for one experienced developer.

---

## PHASE 1 — CRITICAL FIXES (blocks the Grand Finale demo)

### F1. Wire the frontend to the backend (kill the mock layer)

- **Reason:** Verified finding — zero API calls in `frontend/src`; every page renders mock JSON. A jury probing any screen finds a static app, invalidating §5 (Analyst Assurance) and the whole live-demo story. Biggest single SIH-Readiness mover (+12).
- **Files affected:** new `src/lib/api.ts`, `src/lib/useJob.ts` (polling hook); modify `src/pages/DatasetAssurancePage.tsx`, `DashboardPage.tsx`, `ModelAssurancePage.tsx`, `InferenceAssurancePage.tsx`, `AuditReportsPage.tsx`; backend `DatasetController.java` (add list + evidence-image serving endpoints), `AppProperties`/CORS for dev origins.
- **Database changes:** none.
- **Backend changes:** `GET /dataset` (paged list), `GET /dataset/{id}/evidence/image?ref=…` (serves stored evidence images from the artefact store), permissive CORS for `localhost:5173` in dev only.
- **Frontend changes:** typed API client; replace `src/data/*.json` imports with live queries; upload → analyze → poll (job progress) → render real trust score, findings, contributor risks, evidence thumbnails; dashboard KPIs from `GET /overview`.
- **Effort:** 5–6 days.
- **Score impact:** Readiness +12 · Compliance +4 (§5 to near-full) · Architecture +3.

### F2. Distribution drift detection + metadata slicing (feature / class / domain / terrain / season / sensor / illumination)

- **Reason:** Seven explicit PS items at **0% engine coverage** (audit §4 = 0.5/7). The UI charts exist but are fed by mock arrays. Largest compliance mover (+8).
- **Files affected:** new `ai-engine/app/services/detectors/drift.py` (PSI/KS per feature, class-share deltas, metadata slicing); modify `ai-engine/app/services/ingestion.py` (EXIF/sidecar metadata parse — add `Pillow` dep), `ai-engine/app/services/pipeline.py` (pipeline stage + result fields), `ai-engine/app/schemas.py`, `ai-engine/tests/test_drift.py` (new), `backend/.../service/DatasetService.java` + `DatasetAnalysisResponse.java` (map drift), `V2__dataset_drift.sql`, `frontend/src/pages/DatasetAssurancePage.tsx` (bind Distribution card to API).
- **Database changes:** `V2__dataset_drift.sql` — `ALTER TABLE dataset_analysis ADD COLUMN feature_drift jsonb, class_drift jsonb, domain_drift jsonb`.
- **Backend changes:** persist + serve drift structures; response DTO fields `featureDrift[]`, `classDrift[]`, `domainDrift[]`.
- **Frontend changes:** Distribution Analysis card renders API drift (charts already exist — swap the data source); domain-slice chips (terrain/season/sensor/illumination).
- **Effort:** 6–8 days.
- **Score impact:** Compliance +8 (§4 → ~6/7) · Readiness +8.

### F3. Offline deployment bundle (containers + compose + local fonts)

- **Reason:** "Offline / air-gapped" is a scored constraint; today `index.html:13-16` fetches Google Fonts and there is no one-command bring-up (audit §8). Readiness +6, Security +2.
- **Files affected:** new `deploy/docker/{api.Dockerfile,dataset-engine.Dockerfile,model-engine.Dockerfile,provenance-engine.Dockerfile}`, `deploy/compose/docker-compose.yml`, `deploy/config/application-*.yml`, `scripts/bundle-offline.sh` (wheelhouse + npm bundle + image tar); modify `index.html` (remove Google Fonts link), `src/index.css` (`@font-face` for bundled Public Sans woff2), `backend/src/main/resources/application.yml` (env-driven DB/engine hosts).
- **Database changes:** none (Postgres container + Flyway on boot).
- **Backend changes:** none beyond configuration.
- **Frontend changes:** local fonts; production build copied into the API image (single origin).
- **Effort:** 4–5 days.
- **Score impact:** Readiness +6 · Compliance +1 (§8 offline/air-gap) · Security +2.

### F4. Quarantine / Review / Accept action loop

- **Reason:** The analyst decision loop is an explicit PS deliverable; buttons currently dead-end (audit §5). DB state already exists (`QUARANTINED`, `quarantined_at`).
- **Files affected:** modify `backend/.../controller/DatasetController.java`, `service/DatasetService.java`, new `service/AuditSink.java` (stub emitting to log until F7); modify `frontend/src/pages/DatasetAssurancePage.tsx` (Summary buttons), new confirm dialog component.
- **Database changes:** none (columns exist).
- **Backend changes:** `POST /dataset/{id}/quarantine`, `POST /dataset/{id}/review`, `POST /dataset/{id}/accept` with state-transition validation (`UPLOADED/ANALYSED → QUARANTINED`), timestamps set, 409 on invalid transitions.
- **Frontend changes:** buttons call APIs; state badge + banner refresh; disabled state when transition invalid.
- **Effort:** 2–3 days.
- **Score impact:** Compliance +1 (§5) · Readiness +4.

**Phase 1 totals:** ~17–22 dev-days · projected scores after Phase 1: **Compliance ≈ 85 · Architecture ≈ 80 · Security ≈ 68 · SIH Readiness ≈ 84.**

---

## PHASE 2 — IMPORTANT FIXES (platform completeness)

### F5. Model Assurance Spring module (`tv-model`)

- **Reason:** Model engine is standalone; its results are never persisted or surfaced (audit §2 platform gap). Eight PS items become platform-backed.
- **Files affected:** new `backend/.../domain/{Model,ModelVersion,ModelAnalysis,ModelFingerprint,ModelRiskFinding}.java`, `repository/Model*Repository.java`, `dto/ai` extension (model-engine contracts), `service/ModelService.java`, `controller/ModelController.java`, `V2__model_assurance.sql` (or `V3` if F7 lands first); modify `AiEngineClient.java` (assessments API); modify `frontend/src/pages/ModelAssurancePage.tsx`.
- **Database changes:** `V2__model_assurance.sql` — `models`, `model_versions` ( artefact_ref, sha256, framework), `model_analysis` (mode, scores, verdict, result_json), `model_fingerprints`, `model_risk_findings` per docs/db/schema.sql.
- **Backend changes:** `POST /model/upload`, `POST /model/analyze`, `GET /model/{id}`, `GET /model/report/{analysisId}`; persist fingerprints, risk findings, substitution verdict, backdoor risk, limitations.
- **Frontend changes:** Model Assurance page binds to API: upload `.onnx/.pt/.torchscript`, run white/black-box, render fingerprints, substitution verdict, backdoor risk, limitation statement.
- **Effort:** 8–10 days.
- **Score impact:** Compliance +2 (§2 platform-backed) · Architecture +4 · Readiness +5.

### F6. Inference Provenance Spring module (`tv-inference`)

- **Reason:** Provenance records are engine-local; the platform cannot persist, list or audit them (audit §3 platform gap).
- **Files affected:** new `backend/.../domain/{InferenceRequest,InferenceResult,ProvenanceRecord}.java`, repositories, `service/InferenceService.java` (proxy to provenance-engine `/api/v1/provenance/*`), `controller/InferenceController.java`, `V3__inference_provenance.sql`; modify `frontend/src/pages/InferenceAssurancePage.tsx`.
- **Database changes:** `V3__inference_provenance.sql` — `inference_requests`, `inference_results`, `provenance_records` (committed hashes, nonce, signature, chain fields).
- **Backend changes:** `POST /inference/verify` (multipart image+model+config → engine record → persist), `GET /inference/records/{id}`, `GET /inference/chain`.
- **Frontend changes:** Inference page binds to live records: hashes, nonce, signature, verify button, chain view; copy buttons read real values.
- **Effort:** 6–8 days.
- **Score impact:** Compliance +1.5 (§3 platform-backed) · Architecture +3 · Readiness +5.

### F7. Backend audit trail (hash-chained `audit_logs`)

- **Reason:** "Tamper-evident audit trail" must span the platform; the backend currently records nothing (audit §6).
- **Files affected:** new `V4__audit.sql` (`audit_logs` per docs/schema.sql — native enums, hash chain), `service/AuditService.java` (append + chain), emit calls in `DatasetService`/`ModelService`/`InferenceService` state changes, `controller/AuditController.java` (`GET /audit/events`, `GET /audit/verify`), `@Scheduled` verification job.
- **Database changes:** `audit_logs` table + monthly partitions + append-only trigger (UPDATE/DELETE raise).
- **Backend changes:** event emission on upload/analyze/quarantine/report/verify; nightly chain-verification job exposing `GET /audit/verify`.
- **Frontend changes:** Audit & Reports page binds to `GET /audit/events` + shows ledger verification status.
- **Effort:** 4–5 days.
- **Score impact:** Compliance +1 (§6 → 3/3) · Security +6 · Architecture +3.

### F8. Coverage statement (supported / unsupported / assumptions / limitations)

- **Reason:** Explicit PS deliverable ("Limitation Statement"); cheapest high-value item (audit §7 = 1.75/4).
- **Files affected:** new `docs/COVERAGE.md`; all three engines: `GET /coverage` emitting the capability registry (supported attack classes, unsupported classes, assumptions, per-mode limitations); backend passthrough `GET /coverage`; modify `frontend/src/pages/*` (link/section "Coverage Statement").
- **Database changes:** none.
- **Backend changes:** passthrough endpoint aggregating engine coverage documents.
- **Frontend changes:** "Coverage Statement" section rendered on each assurance page.
- **Effort:** 1–2 days.
- **Score impact:** Compliance +1.75 (§7 → full) · Readiness +3.

### F9. Authentication & RBAC

- **Reason:** Zero authn/authz on any API (audit Security finding); SIH evaluators test for it first on the security axis.
- **Files affected:** modify `backend/pom.xml` (+spring-boot-starter-security), new `security/SecurityConfig.java`, `security/JwtService.java`, `controller/AuthController.java` (`POST /auth/login`), `users` password flows; enforce engine `X-API-Key` (set `TVA_API_KEY`/`TVP_API_KEY`, backend sends keys); modify `frontend/src/pages` (login page, 401 interceptor, role-gated quarantine buttons).
- **Database changes:** seed demo users with bcrypt hashes in migration (or V5 update).
- **Backend changes:** stateless JWT filter chain; `@PreAuthorize` roles (ADMIN/AUDITOR/ANALYST/VIEWER) per module; engine clients attach API keys.
- **Frontend changes:** login view, token storage, Authorization header, role-aware UI.
- **Effort:** 4–6 days.
- **Score impact:** Security +12 · Readiness +3.

**Phase 2 totals:** ~23–31 dev-days · projected scores after Phase 2: **Compliance ≈ 90 · Architecture ≈ 88 · Security ≈ 85 · SIH Readiness ≈ 90.**

---

## PHASE 3 — NICE TO HAVE (polish and hardening)

### F10. Recommended-action generation

- **Reason:** §5 item currently mock-only; engines should emit actions per trust level and finding.
- **Files affected:** `ai-engine/app/services/trust.py` + `model-engine/app/services/assessment.py` (action rules), schemas; backend persist + expose; frontend render list.
- **Database changes:** none (JSON payload field).
- **Backend changes:** map `recommended_actions` into analysis/report payloads.
- **Frontend changes:** Assurance Summary renders engine actions instead of static ones.
- **Effort:** 2 days.
- **Score impact:** Compliance +1 (§5 full).

### F11. PDF report rendering

- **Reason:** Reports are JSON artefacts; evaluators expect a downloadable signed PDF.
- **Files affected:** `backend/pom.xml` (+PDFBox), new `service/ReportRenderService.java`, `GET /dataset/report/download/{id}`.
- **Database changes:** none (format=PDF row update).
- **Backend changes:** template render (classification header, trust ring, findings table, evidence appendix, signature block).
- **Frontend changes:** "Download Report" on the summary panel.
- **Effort:** 3–4 days.
- **Score impact:** Readiness +2 · Compliance +0.5.

### F12. COCO ingestion test

- **Reason:** COCO loader is implemented but untested (audit §8 caveat).
- **Files affected:** `ai-engine/tests/test_coco.py` (COCO fixture mirroring the YOLO one).
- **Database changes:** none. **Backend changes:** none. **Frontend changes:** none.
- **Effort:** 1 day.
- **Score impact:** Compliance +0.5 (§8 evidence).

### F13. Monorepo migration

- **Reason:** Adopt `frontend/` layout per ARCHITECTURE.md §5; removes the structure deviation.
- **Files affected:** move root frontend files → `frontend/`; update `docs/ARCHITECTURE.md`, root README, CI/scripts.
- **Database changes:** none. **Backend changes:** none. **Frontend changes:** import paths only.
- **Effort:** 1–2 days.
- **Score impact:** Architecture +3.

### F14. SSE job progress + rate limiting + key hardening

- **Reason:** Live progress replaces polling; minor security hardening (per-IP limits, key file permissions note).
- **Files affected:** backend `SseController`/job events, engines optional SSE; bucket4j dep; docs.
- **Database changes:** none. **Backend changes:** SSE emitter on job store updates. **Frontend changes:** EventSource hook fallback to polling.
- **Effort:** 3–4 days.
- **Score impact:** Readiness +1 · Security +2.

**Phase 3 totals:** ~10–13 dev-days · projected scores after Phase 3: **Compliance ≈ 95 · Architecture ≈ 92 · Security ≈ 88 · SIH Readiness ≈ 95.**

---

## Score trajectory

| Milestone | Compliance | Architecture | Security | SIH Readiness |
|---|---|---|---|---|
| Current (audited) | 72 | 76 | 66 | 64 |
| After Phase 1 | 85 | 80 | 68 | 84 |
| After Phase 2 | 90 | 88 | 85 | 90 |
| After Phase 3 | 95 | 92 | 88 | 95 |

## Dependency order

F3 → (F1, F5, F6) → F4 → F7 → F2 (independent, start anytime) · F8 any time · F9 after F1 · F10–F14 last.
