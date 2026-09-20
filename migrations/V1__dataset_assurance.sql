-- TRUSTVISION · Dataset Assurance module schema (v1)
-- Aligned with docs/db/schema.sql and docs/ARCHITECTURE.md §6.

-- ---------------------------------------------------------------------------
-- Enumerated domains
-- ---------------------------------------------------------------------------

CREATE TYPE user_role            AS ENUM ('ADMIN','AUDITOR','ANALYST','VIEWER');
CREATE TYPE user_status          AS ENUM ('ACTIVE','DISABLED','LOCKED');
CREATE TYPE auth_source          AS ENUM ('LOCAL','LDAP');
CREATE TYPE classification_level AS ENUM ('UNCLASSIFIED','OFFICIAL','OFFICIAL_SENSITIVE','SECRET');
CREATE TYPE dataset_format       AS ENUM ('COCO','YOLO');
CREATE TYPE dataset_state        AS ENUM ('UPLOADED','ANALYSING','ANALYSED','QUARANTINED','REJECTED');
CREATE TYPE job_status           AS ENUM ('QUEUED','RUNNING','COMPLETED','FAILED');
CREATE TYPE risk_level           AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');
CREATE TYPE provenance_subject   AS ENUM ('DATASET','MODEL','INFERENCE');
CREATE TYPE report_type          AS ENUM ('ASSESSMENT','AUDIT_EXPORT','COMPLIANCE');
CREATE TYPE report_format        AS ENUM ('PDF','CSV','JSON');

-- ---------------------------------------------------------------------------
-- users (minimal: full identity lives in the tv-identity module)
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id            uuid PRIMARY KEY,
    username      text NOT NULL UNIQUE,
    full_name     text NOT NULL,
    role          user_role NOT NULL DEFAULT 'ANALYST',
    clearance     classification_level NOT NULL DEFAULT 'OFFICIAL',
    auth_source   auth_source NOT NULL DEFAULT 'LOCAL',
    password_hash text,
    status        user_status NOT NULL DEFAULT 'ACTIVE',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- seeded service account used as actor until the identity module lands
INSERT INTO users (id, username, full_name, role, clearance, auth_source, password_hash, status)
VALUES ('00000000-0000-0000-0000-000000000001', 'system', 'System Service Account',
        'ADMIN', 'SECRET', 'LOCAL', '!', 'ACTIVE');

-- ---------------------------------------------------------------------------
-- datasets
-- ---------------------------------------------------------------------------

CREATE TABLE datasets (
    id             uuid PRIMARY KEY,
    name           text NOT NULL,
    codename       text,
    version        integer NOT NULL DEFAULT 1,
    format         dataset_format NOT NULL,
    classification classification_level NOT NULL DEFAULT 'OFFICIAL',
    owner_id       uuid NOT NULL REFERENCES users(id),
    supersedes_id  uuid REFERENCES datasets(id),
    artefact_ref   text NOT NULL,
    sha256         char(64) NOT NULL,
    size_bytes     bigint NOT NULL CHECK (size_bytes >= 0),
    image_count    integer,
    class_count    integer,
    state          dataset_state NOT NULL DEFAULT 'UPLOADED',
    quarantined_at timestamptz,
    notes          text,
    uploaded_at    timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT datasets_sha256_fmt CHECK (sha256 ~ '^[0-9a-f]{64}$')
);
CREATE INDEX idx_datasets_owner ON datasets(owner_id);
CREATE INDEX idx_datasets_format_state ON datasets(format, state);

-- ---------------------------------------------------------------------------
-- dataset_analysis (stored analysis results)
-- ---------------------------------------------------------------------------

CREATE TABLE dataset_analysis (
    id                          uuid PRIMARY KEY,
    dataset_id                  uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    status                      job_status NOT NULL DEFAULT 'QUEUED',
    engine_job_id               text,
    duplicates_count            integer,
    flood_count                 integer,
    label_flip_count            integer,
    systematic_mislabel_count   integer,
    trigger_count               integer,
    ood_count                   integer,
    trust_score                 numeric(5,2),
    risk_level                  risk_level,
    component_scores            jsonb,
    limitations                 jsonb,
    result_json                 jsonb,
    result_sha256               char(64),
    error                       text,
    started_at                  timestamptz,
    completed_at                timestamptz,
    requested_by                uuid REFERENCES users(id),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dataset_analysis_score_chk
        CHECK (trust_score IS NULL OR trust_score BETWEEN 0 AND 100)
);
CREATE INDEX idx_dataset_analysis_dataset ON dataset_analysis(dataset_id, created_at DESC);
CREATE INDEX idx_dataset_analysis_active  ON dataset_analysis(status) WHERE status <> 'COMPLETED';

-- ---------------------------------------------------------------------------
-- contributors + contributor_risk (contributor risk scoring)
-- ---------------------------------------------------------------------------

CREATE TABLE contributors (
    id         uuid PRIMARY KEY,
    name       text NOT NULL UNIQUE,
    unit       text,
    active     boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contributor_risk (
    id                  uuid PRIMARY KEY,
    dataset_analysis_id uuid NOT NULL REFERENCES dataset_analysis(id) ON DELETE CASCADE,
    contributor_id      uuid NOT NULL REFERENCES contributors(id),
    samples_contributed integer NOT NULL CHECK (samples_contributed >= 0),
    risk_score          numeric(5,2) NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level          risk_level NOT NULL,
    factors             jsonb NOT NULL DEFAULT '{}',
    flagged             boolean NOT NULL DEFAULT false,
    assessed_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT contributor_risk_uq UNIQUE (dataset_analysis_id, contributor_id)
);
CREATE INDEX idx_contributor_risk_flagged ON contributor_risk(risk_level) WHERE flagged;

-- ---------------------------------------------------------------------------
-- dataset_evidence (stored evidence)
-- ---------------------------------------------------------------------------

CREATE TABLE dataset_evidence (
    id                  uuid PRIMARY KEY,
    dataset_analysis_id uuid NOT NULL REFERENCES dataset_analysis(id) ON DELETE CASCADE,
    finding_id          text NOT NULL,
    detector            text NOT NULL,
    title               text NOT NULL,
    description         text,
    severity            risk_level NOT NULL,
    confidence          numeric(5,2),
    sample_count        integer NOT NULL DEFAULT 0,
    contributors        jsonb NOT NULL DEFAULT '[]',
    image_paths         text[] NOT NULL DEFAULT '{}',
    detail              jsonb NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_dataset_evidence_analysis ON dataset_evidence(dataset_analysis_id);

-- ---------------------------------------------------------------------------
-- assurance_reports
-- ---------------------------------------------------------------------------

CREATE TABLE assurance_reports (
    id                  uuid PRIMARY KEY,
    report_type         report_type NOT NULL,
    format              report_format NOT NULL DEFAULT 'JSON',
    title               text NOT NULL,
    subject_type        provenance_subject NOT NULL,
    subject_id          uuid NOT NULL,
    dataset_analysis_id uuid REFERENCES dataset_analysis(id),
    trust_score         numeric(5,2),
    risk_level          risk_level,
    artefact_ref        text NOT NULL,
    sha256              char(64) NOT NULL,
    generated_by        uuid NOT NULL REFERENCES users(id),
    generated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_subject ON assurance_reports(subject_type, subject_id);
CREATE INDEX idx_reports_analysis ON assurance_reports(dataset_analysis_id);
