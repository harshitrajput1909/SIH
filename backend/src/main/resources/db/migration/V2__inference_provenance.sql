-- TRUSTVISION · Inference Provenance module schema (v2)
-- Aligned with docs/db/schema.sql (inference_requests / inference_results /
-- provenance_records). The FastAPI provenance engine owns the authoritative
-- chain; these tables persist the platform-side copies and verification results.

-- ---------------------------------------------------------------------------
-- inference_requests (one row per verification call; stores the hashes)
-- ---------------------------------------------------------------------------

CREATE TABLE inference_requests (
    id             uuid PRIMARY KEY,
    image_ref      text NOT NULL,
    image_sha256   char(64) NOT NULL,
    model_ref      text NOT NULL,
    model_sha256   char(64) NOT NULL,
    config_ref     text,
    config_sha256  char(64),
    output_ref     text,
    output_sha256  char(64),
    nonce          text,                    -- assigned by the provenance engine
    record_id      text,
    requested_by   uuid NOT NULL REFERENCES users(id),
    requested_at   timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inference_image_sha_fmt  CHECK (image_sha256  ~ '^[0-9a-f]{64}$'),
    CONSTRAINT inference_model_sha_fmt  CHECK (model_sha256  ~ '^[0-9a-f]{64}$'),
    CONSTRAINT inference_config_sha_fmt CHECK (config_sha256 IS NULL OR config_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT inference_output_sha_fmt CHECK (output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE INDEX idx_inference_requests_nonce  ON inference_requests(nonce);
CREATE INDEX idx_inference_requests_record ON inference_requests(record_id);

-- ---------------------------------------------------------------------------
-- provenance_records (platform copy of the engine's hash-chained record;
-- append-only — UPDATE/DELETE refused)
-- ---------------------------------------------------------------------------

CREATE TABLE provenance_records (
    id                uuid PRIMARY KEY,
    request_id        uuid REFERENCES inference_requests(id),
    record_id         text NOT NULL UNIQUE,
    record_type       text NOT NULL,
    record_timestamp  timestamptz NOT NULL,
    artifacts         jsonb NOT NULL,
    nonce             text NOT NULL,
    prev_hash         char(64),
    verification_hash char(64) NOT NULL,
    signature         jsonb NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT provenance_vh_fmt CHECK (verification_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT provenance_prev_fmt CHECK (prev_hash IS NULL OR prev_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX idx_provenance_request ON provenance_records(request_id);

CREATE OR REPLACE FUNCTION provenance_records_block_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'provenance_records is append-only: % on % is not permitted', TG_OP, TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_provenance_no_mutation
    BEFORE UPDATE OR DELETE ON provenance_records
    FOR EACH ROW EXECUTE FUNCTION provenance_records_block_mutation();

-- ---------------------------------------------------------------------------
-- inference_verifications (stored verification results)
-- ---------------------------------------------------------------------------

CREATE TABLE inference_verifications (
    id          uuid PRIMARY KEY,
    request_id  uuid NOT NULL REFERENCES inference_requests(id) ON DELETE CASCADE,
    record_id   text NOT NULL,
    valid       boolean NOT NULL,
    checks      jsonb NOT NULL,
    details     jsonb NOT NULL DEFAULT '{}',
    verified_by uuid NOT NULL REFERENCES users(id),
    verified_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_inference_verifications_request ON inference_verifications(request_id);
