-- =============================================================================
-- TRUSTVISION — AI Integrity Assurance Platform
-- PostgreSQL schema v1.0  (PostgreSQL 16+)
--
-- Design notes
--   * Audit trail ............ audit_logs is append-only (trigger-blocked
--                              UPDATE/DELETE), hash-chained, range-partitioned.
--   * Cryptographic provenance provenance_records chains per subject with
--                              prev_hash/entry_hash; model_fingerprints carry
--                              artefact digests; sha256 columns everywhere.
--   * Contributor risk ....... contributors (entity) + contributor_risk
--                              (score snapshot per dataset analysis).
--   * White/black-box ........ model_analysis.assessment_mode with a CHECK
--                              that forces white-box runs to carry graph-level
--                              evidence (graph hash + op-allowlist result).
--   * UUID primary keys ...... gen_random_uuid() (v4). If the cluster runs
--                              PostgreSQL 18+, swap to uuidv7() for
--                              time-ordered keys; application may also supply v7.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), digest()

-- =============================================================================
-- ENUMERATED DOMAINS
-- =============================================================================

CREATE TYPE user_role              AS ENUM ('ADMIN','AUDITOR','ANALYST','VIEWER');
CREATE TYPE user_status            AS ENUM ('ACTIVE','DISABLED','LOCKED');
CREATE TYPE classification_level   AS ENUM ('UNCLASSIFIED','OFFICIAL','OFFICIAL_SENSITIVE','SECRET');
CREATE TYPE auth_source            AS ENUM ('LOCAL','LDAP');

CREATE TYPE dataset_format         AS ENUM ('COCO','YOLO');
CREATE TYPE dataset_state          AS ENUM ('UPLOADED','ANALYSING','ANALYSED','QUARANTINED','REJECTED');

CREATE TYPE job_status             AS ENUM ('QUEUED','RUNNING','COMPLETED','FAILED');
CREATE TYPE risk_level             AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');

CREATE TYPE dataset_finding_type   AS ENUM ('DUPLICATE','CORRUPTED','MISSING_LABEL','SUSPICIOUS');
CREATE TYPE anomaly_type           AS ENUM ('LABEL_FLIP','DUPLICATE_CLUSTER','BACKDOOR_TRIGGER','OUT_OF_DISTRIBUTION');

CREATE TYPE model_framework        AS ENUM ('ONNX','PYTORCH','TORCHSCRIPT');
CREATE TYPE model_state            AS ENUM ('REGISTERED','ANALYSING','ANALYSED','QUARANTINED','REJECTED');
CREATE TYPE assessment_mode        AS ENUM ('WHITE_BOX','BLACK_BOX');
CREATE TYPE model_finding_type     AS ENUM ('BACKDOOR','ADVERSARIAL_ROBUSTNESS','PREDICTION_DRIFT','CONFIDENCE_DRIFT');
CREATE TYPE training_source        AS ENUM ('CORE_TRAINING','FINE_TUNING','EXTERNAL_WEIGHTS','DATA_AUGMENTATION');
CREATE TYPE access_verdict         AS ENUM ('ACCESSIBLE','LIMITED');
CREATE TYPE fingerprint_type       AS ENUM ('FILE_SHA256','WEIGHT_SHA256','ONNX_GRAPH_HASH','TORCHSCRIPT_CODE_HASH','LAYER_STAT_VECTOR');

CREATE TYPE inference_verdict      AS ENUM ('TRUSTED','SUSPICIOUS','FLAGGED');
CREATE TYPE integrity_check_type   AS ENUM ('IMAGE_TAMPERING','ADVERSARIAL_NOISE','MANIPULATION_RISK','REPLAY_ATTACK');

CREATE TYPE provenance_type        AS ENUM ('INPUT_SHA256','MODEL_DIGEST','CONFIG_HASH','NONCE','HMAC_SIGNATURE','DIGITAL_SIGNATURE','CHAIN_ENTRY');
CREATE TYPE provenance_subject     AS ENUM ('DATASET','MODEL','INFERENCE');

CREATE TYPE coverage_type          AS ENUM ('SAMPLE_COVERAGE','CLASS_COVERAGE','OPERATION_COVERAGE','DOMAIN_COVERAGE','COMPLIANCE_CLAUSE');
CREATE TYPE coverage_status        AS ENUM ('ACTIVE','SUPERSEDED','REVOKED');

CREATE TYPE report_type            AS ENUM ('ASSESSMENT','AUDIT_EXPORT','COMPLIANCE');
CREATE TYPE report_format          AS ENUM ('PDF','CSV','JSON');

CREATE TYPE audit_outcome          AS ENUM ('SUCCESS','FAILURE','DENIED');
CREATE TYPE contributor_org_type   AS ENUM ('INTERNAL_UNIT','CONTRACTOR','VENDOR','RESEARCH_LAB','OTHER');

-- =============================================================================
-- 1. USERS
-- =============================================================================

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username      text NOT NULL UNIQUE,
    full_name     text NOT NULL,
    email         text,
    role          user_role            NOT NULL DEFAULT 'ANALYST',
    clearance     classification_level NOT NULL DEFAULT 'OFFICIAL',
    auth_source   auth_source          NOT NULL DEFAULT 'LOCAL',
    password_hash text,                              -- NULL when auth_source = 'LDAP'
    status        user_status          NOT NULL DEFAULT 'ACTIVE',
    last_login_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_local_password_chk
        CHECK (auth_source <> 'LOCAL' OR password_hash IS NOT NULL)
);

-- =============================================================================
-- 2. CONTRIBUTORS  (data-supply chain entities)
-- =============================================================================

CREATE TABLE contributors (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL UNIQUE,
    unit       text,
    org_type   contributor_org_type NOT NULL DEFAULT 'INTERNAL_UNIT',
    contact    text,
    clearance  classification_level,
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- 3. DATASETS  (one row per registered artefact version; self-FK = lineage)
-- =============================================================================

CREATE TABLE datasets (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name           text NOT NULL,
    codename       text,
    version        integer NOT NULL DEFAULT 1,
    format         dataset_format NOT NULL,          -- COCO | YOLO
    classification classification_level NOT NULL DEFAULT 'OFFICIAL',
    owner_id       uuid NOT NULL REFERENCES users(id),
    supersedes_id  uuid REFERENCES datasets(id),     -- previous version lineage
    artefact_ref   text NOT NULL,                    -- path/key in the artefact store
    sha256         char(64) NOT NULL,
    size_bytes     bigint  NOT NULL CHECK (size_bytes >= 0),
    image_count    integer,
    class_count    integer,
    state          dataset_state NOT NULL DEFAULT 'UPLOADED',
    quarantined_at timestamptz,
    notes          text,
    uploaded_at    timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT datasets_sha256_fmt  CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT datasets_lineage_chk CHECK (supersedes_id <> id)
);

-- =============================================================================
-- 4. DATASET_ANALYSIS  (one row per analysis run; aggregates + result hash)
-- =============================================================================

CREATE TABLE dataset_analysis (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id       uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    status           job_status NOT NULL DEFAULT 'QUEUED',
    engine_job_id    text,                              -- job id inside the AI engine

    -- quality aggregates
    duplicates_count     integer,
    duplicates_pct       numeric(5,2),
    corrupted_count      integer,
    corrupted_pct        numeric(5,2),
    missing_labels_count integer,
    missing_labels_pct   numeric(5,2),
    suspicious_count     integer,
    suspicious_pct       numeric(5,2),

    -- drift aggregates
    feature_drift_max_psi numeric(6,3),
    class_drift_max_delta numeric(6,3),
    domain_drift          jsonb,          -- [{"domain":"Night","drift":68}, …]

    -- anomaly counts
    label_flips        integer,
    duplicate_clusters integer,
    backdoor_triggers  integer,
    ood_samples        integer,

    -- outcome
    trust_score      numeric(5,2) CHECK (trust_score BETWEEN 0 AND 100),
    risk_level       risk_level,
    component_scores jsonb,             -- {"integrity":66,"provenance":71,…}
    findings_detail  jsonb,             -- per-finding detail + evidence image refs
    result_sha256    char(64),          -- hash of the canonical result document
    error            text,

    started_at       timestamptz,
    completed_at     timestamptz,
    requested_by     uuid REFERENCES users(id),
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT dataset_analysis_result_chk
        CHECK ((status = 'COMPLETED') = (completed_at IS NOT NULL)),
    CONSTRAINT dataset_analysis_result_hash_fmt
        CHECK (result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 5. CONTRIBUTOR_RISK  (risk score snapshot per analysis run)
-- =============================================================================

CREATE TABLE contributor_risk (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_analysis_id uuid NOT NULL REFERENCES dataset_analysis(id) ON DELETE CASCADE,
    contributor_id      uuid NOT NULL REFERENCES contributors(id),
    samples_contributed integer NOT NULL CHECK (samples_contributed >= 0),
    risk_score          numeric(5,2) NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level          risk_level NOT NULL,
    factors             jsonb NOT NULL DEFAULT '{}',   -- score breakdown (weights, inputs)
    flagged             boolean NOT NULL DEFAULT false,
    assessed_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contributor_risk_uq UNIQUE (dataset_analysis_id, contributor_id)
);

-- =============================================================================
-- 6. MODELS  (ONNX / PyTorch / TorchScript; self-FK = lineage)
-- =============================================================================

CREATE TABLE models (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name           text NOT NULL,
    version        integer NOT NULL DEFAULT 1,
    framework      model_framework NOT NULL,          -- ONNX | PYTORCH | TORCHSCRIPT
    task           text,                              -- e.g. OBJECT_DETECTION
    architecture   text,                              -- e.g. CSPDarknet
    params         bigint,
    input_size     text,                              -- e.g. '640x640'
    owner_id       uuid NOT NULL REFERENCES users(id),
    supersedes_id  uuid REFERENCES models(id),
    artefact_ref   text NOT NULL,
    sha256         char(64) NOT NULL,
    size_bytes     bigint  NOT NULL CHECK (size_bytes >= 0),
    state          model_state NOT NULL DEFAULT 'REGISTERED',
    quarantined_at timestamptz,
    notes          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT models_sha256_fmt  CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT models_lineage_chk CHECK (supersedes_id <> id)
);

-- =============================================================================
-- 7. MODEL_ANALYSIS  (white-box and black-box assessments)
-- =============================================================================

CREATE TABLE model_analysis (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id            uuid NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    assessment_mode     assessment_mode NOT NULL,    -- WHITE_BOX | BLACK_BOX
    status              job_status NOT NULL DEFAULT 'QUEUED',
    engine_job_id       text,

    -- white-box evidence (NULL for black-box runs)
    graph_hash              char(64),
    op_allowlist_violations integer,
    pickle_risk             boolean,                 -- unsafe serialisation detected

    -- risk scores 0–100 (black-box probes fill these without graph access)
    backdoor_score          numeric(5,2) CHECK (backdoor_score         BETWEEN 0 AND 100),
    adversarial_score       numeric(5,2) CHECK (adversarial_score      BETWEEN 0 AND 100),
    prediction_drift_score  numeric(5,2) CHECK (prediction_drift_score BETWEEN 0 AND 100),
    confidence_drift_score  numeric(5,2) CHECK (confidence_drift_score BETWEEN 0 AND 100),

    -- training provenance risk
    training_sources    jsonb,            -- [{"source":"EXTERNAL_WEIGHTS","risk_level":"HIGH"}]
    access_verdict      access_verdict,   -- ACCESSIBLE (white-box) | LIMITED (black-box)

    trust_score         numeric(5,2) CHECK (trust_score BETWEEN 0 AND 100),
    risk_level          risk_level,
    findings_detail     jsonb,
    result_sha256       char(64),
    error               text,

    started_at          timestamptz,
    completed_at        timestamptz,
    requested_by        uuid REFERENCES users(id),
    created_at          timestamptz NOT NULL DEFAULT now(),

    -- a WHITE_BOX assessment must carry graph-level evidence
    CONSTRAINT model_analysis_whitebox_evidence_chk CHECK (
        assessment_mode <> 'WHITE_BOX'
        OR (graph_hash IS NOT NULL AND op_allowlist_violations IS NOT NULL)
    ),
    CONSTRAINT model_analysis_result_chk
        CHECK ((status = 'COMPLETED') = (completed_at IS NOT NULL)),
    CONSTRAINT model_analysis_result_hash_fmt
        CHECK (result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 8. MODEL_FINGERPRINTS  (cryptographic identity of model artefacts)
-- =============================================================================

CREATE TABLE model_fingerprints (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id          uuid NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    model_analysis_id uuid REFERENCES model_analysis(id) ON DELETE SET NULL,
    fingerprint_type  fingerprint_type NOT NULL,
    algorithm         text NOT NULL DEFAULT 'SHA-256',
    value             char(64) NOT NULL,               -- hex digest
    details           jsonb,                           -- e.g. per-layer stat vector
    computed_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_fingerprints_uq UNIQUE (model_id, fingerprint_type, value),
    CONSTRAINT model_fingerprints_value_fmt CHECK (value ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 9. INFERENCE_RECORDS  (verified inference outputs)
-- =============================================================================

CREATE TABLE inference_records (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id          uuid NOT NULL REFERENCES models(id),
    dataset_id        uuid REFERENCES datasets(id),  -- optional operational context
    image_ref         text NOT NULL,
    image_sha256      char(64) NOT NULL,
    predicted_label   text NOT NULL,
    confidence        numeric(5,2) CHECK (confidence BETWEEN 0 AND 100),
    verdict           inference_verdict NOT NULL,    -- TRUSTED | SUSPICIOUS | FLAGGED
    integrity_summary jsonb,                         -- [{check,verdict,score}]
    nonce             text,                          -- single-use verification nonce
    request_hmac      char(64),                      -- HMAC over request context
    verified_by       uuid NOT NULL REFERENCES users(id),
    executed_at       timestamptz NOT NULL,          -- when the model produced the output
    verified_at       timestamptz NOT NULL DEFAULT now(),
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inference_records_image_fmt   CHECK (image_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT inference_records_hmac_fmt    CHECK (request_hmac IS NULL OR request_hmac ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 10. PROVENANCE_RECORDS  (hash-chained cryptographic provenance per subject)
-- =============================================================================

CREATE TABLE provenance_records (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type        provenance_subject NOT NULL,             -- DATASET | MODEL | INFERENCE
    subject_id          uuid NOT NULL,                           -- polymorphic FK
    inference_record_id uuid REFERENCES inference_records(id) ON DELETE CASCADE,
    record_type         provenance_type NOT NULL,                -- INPUT_SHA256, MODEL_DIGEST, NONCE, …
    algorithm           text NOT NULL DEFAULT 'SHA-256',
    value               text NOT NULL,                           -- hex digest / nonce / signature
    prev_hash           char(64),                                -- hash of previous chain entry
    entry_hash          char(64) NOT NULL,                       -- SHA-256(prev_hash ‖ canonical(record))
    signature           text,                                    -- detached signature by issuer key
    signed_by           uuid REFERENCES users(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT provenance_entry_hash_fmt CHECK (entry_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT provenance_prev_hash_fmt  CHECK (prev_hash   IS NULL OR prev_hash ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 11. COVERAGE_STATEMENTS  (what an assessment did — and did not — cover)
-- =============================================================================

CREATE TABLE coverage_statements (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type        provenance_subject NOT NULL,
    subject_id          uuid NOT NULL,
    dataset_analysis_id uuid REFERENCES dataset_analysis(id) ON DELETE CASCADE,
    model_analysis_id   uuid REFERENCES model_analysis(id) ON DELETE CASCADE,
    coverage_type       coverage_type NOT NULL,
    coverage_pct        numeric(5,2) CHECK (coverage_pct BETWEEN 0 AND 100),
    scope               jsonb NOT NULL DEFAULT '{}', -- included/excluded classes, ops, domains
    statement           text NOT NULL,               -- human-readable assertion
    limitations         text,
    status              coverage_status NOT NULL DEFAULT 'ACTIVE',
    issued_by           uuid NOT NULL REFERENCES users(id),
    issued_at           timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz,
    superseded_by       uuid REFERENCES coverage_statements(id)
);

-- =============================================================================
-- 12. ASSURANCE_REPORTS  (signed PDF/CSV deliverables)
-- =============================================================================

CREATE TABLE assurance_reports (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type         report_type NOT NULL,            -- ASSESSMENT | AUDIT_EXPORT | COMPLIANCE
    format              report_format NOT NULL DEFAULT 'PDF',
    title               text NOT NULL,
    subject_type        provenance_subject NOT NULL,
    subject_id          uuid NOT NULL,
    dataset_analysis_id uuid REFERENCES dataset_analysis(id),
    model_analysis_id   uuid REFERENCES model_analysis(id),
    trust_score         numeric(5,2),                    -- snapshot at generation time
    risk_level          risk_level,
    coverage_ids        uuid[] NOT NULL DEFAULT '{}',    -- coverage statements included (no FK on arrays)
    artefact_ref        text NOT NULL,
    sha256              char(64) NOT NULL,
    signature           text,                            -- detached signature (internal CA key)
    signed_by           text,                            -- signing key identifier
    generated_by        uuid NOT NULL REFERENCES users(id),
    generated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT assurance_reports_sha256_fmt CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

-- =============================================================================
-- 13. AUDIT_LOGS  (append-only, hash-chained, monthly range partitions)
-- =============================================================================

CREATE TABLE audit_logs (
    id          bigint GENERATED ALWAYS AS IDENTITY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_id    uuid REFERENCES users(id),               -- NULL = system actor
    actor_name  text NOT NULL,
    module      text NOT NULL,                           -- IDENTITY|DATASET|MODEL|INFERENCE|AUDIT|REPORT
    action      text NOT NULL,                           -- e.g. DATASET_UPLOADED, MODEL_QUARANTINED
    target_type text,
    target_id   uuid,
    outcome     audit_outcome NOT NULL DEFAULT 'SUCCESS',
    details     jsonb,
    ip_address  inet,
    prev_hash   char(64),                                -- hash of previous ledger entry
    entry_hash  char(64) NOT NULL,                       -- SHA-256(prev_hash ‖ canonical(entry))
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;
CREATE TABLE audit_logs_2026_09 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
-- (a scheduled job creates future monthly partitions ahead of time)

-- Append-only enforcement: reject UPDATE and DELETE at the database level.
CREATE OR REPLACE FUNCTION audit_logs_block_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: % on % is not permitted', TG_OP, TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER audit_logs_no_mutation
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_block_mutation();

-- =============================================================================
-- updated_at maintenance
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated_at       BEFORE UPDATE ON users        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_datasets_updated_at    BEFORE UPDATE ON datasets     FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_models_updated_at      BEFORE UPDATE ON models       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_contributors_updated_at BEFORE UPDATE ON contributors FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- INDEXES
-- =============================================================================

-- datasets
CREATE INDEX idx_datasets_owner        ON datasets (owner_id);
CREATE INDEX idx_datasets_format_state ON datasets (format, state);
CREATE INDEX idx_datasets_sha256       ON datasets (sha256);            -- duplicate-ingest detection
CREATE INDEX idx_datasets_supersedes   ON datasets (supersedes_id);     -- version lineage walk

-- dataset_analysis
CREATE INDEX idx_dataset_analysis_dataset ON dataset_analysis (dataset_id, created_at DESC);
CREATE INDEX idx_dataset_analysis_active  ON dataset_analysis (status) WHERE status <> 'COMPLETED';

-- contributor_risk
CREATE INDEX idx_contributor_risk_contributor ON contributor_risk (contributor_id);
CREATE INDEX idx_contributor_risk_flagged     ON contributor_risk (risk_level) WHERE flagged;

-- models
CREATE INDEX idx_models_owner          ON models (owner_id);
CREATE INDEX idx_models_framework_state ON models (framework, state);
CREATE INDEX idx_models_sha256         ON models (sha256);
CREATE INDEX idx_models_supersedes     ON models (supersedes_id);

-- model_analysis
CREATE INDEX idx_model_analysis_model ON model_analysis (model_id, created_at DESC);
CREATE INDEX idx_model_analysis_mode  ON model_analysis (assessment_mode);

-- model_fingerprints
CREATE INDEX idx_model_fingerprints_model ON model_fingerprints (model_id);
CREATE INDEX idx_model_fingerprints_value ON model_fingerprints (value);      -- fingerprint lookup

-- inference_records
CREATE INDEX idx_inference_model_time ON inference_records (model_id, executed_at DESC);
CREATE INDEX idx_inference_verdict    ON inference_records (verdict);
CREATE INDEX idx_inference_image      ON inference_records (image_sha256);

-- provenance_records
CREATE INDEX idx_provenance_subject  ON provenance_records (subject_type, subject_id, created_at);
CREATE INDEX idx_provenance_inference ON provenance_records (inference_record_id);

-- audit_logs (declared on the parent; propagated to every partition)
CREATE INDEX idx_audit_occurred     ON audit_logs (occurred_at DESC);
CREATE INDEX idx_audit_actor        ON audit_logs (actor_id);
CREATE INDEX idx_audit_module_action ON audit_logs (module, action);
CREATE INDEX idx_audit_target       ON audit_logs (target_type, target_id);

-- coverage_statements
CREATE INDEX idx_coverage_subject ON coverage_statements (subject_type, subject_id);
CREATE INDEX idx_coverage_status  ON coverage_statements (status);

-- assurance_reports
CREATE INDEX idx_reports_subject  ON assurance_reports (subject_type, subject_id);
CREATE INDEX idx_reports_generated ON assurance_reports (generated_at DESC);

COMMIT;

-- =============================================================================
-- TABLE COMMENTS
-- =============================================================================
COMMENT ON TABLE users              IS 'Platform accounts; RBAC role and clearance level';
COMMENT ON TABLE contributors       IS 'Data supply-chain entities contributing to datasets';
COMMENT ON TABLE datasets           IS 'Registered dataset artefacts (COCO/YOLO), one row per version; supersedes_id = lineage';
COMMENT ON TABLE dataset_analysis   IS 'One analysis run per row; aggregate quality/drift/anomaly results, trust score, result hash';
COMMENT ON TABLE contributor_risk   IS 'Contributor risk score snapshot per dataset analysis (supports scoring auditability)';
COMMENT ON TABLE models             IS 'Registered model artefacts (ONNX/PyTorch/TorchScript), one row per version';
COMMENT ON TABLE model_analysis     IS 'White-box or black-box assessment run with risk scores and white-box evidence check';
COMMENT ON TABLE model_fingerprints IS 'Cryptographic fingerprints of model artefacts (file, weights, graph, code, stats)';
COMMENT ON TABLE inference_records  IS 'Verified inference outputs with verdict, confidence and request HMAC';
COMMENT ON TABLE provenance_records IS 'Hash-chained cryptographic provenance entries per subject (dataset/model/inference)';
COMMENT ON TABLE coverage_statements IS 'Assertions of assessment coverage and limitations attached to analyses';
COMMENT ON TABLE assurance_reports  IS 'Signed assurance report deliverables with subject snapshot';
COMMENT ON TABLE audit_logs         IS 'Append-only hash-chained audit ledger, range-partitioned by month';
