# TRUSTVISION — Dataset Assurance API (Spring Boot 3 / Java 21)

Backend for the Dataset Assurance module: ingests COCO/YOLO dataset archives,
drives the offline FastAPI analysis engine, and stores **analysis results,
contributor risk scores, evidence and signed assurance reports** in PostgreSQL.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/dataset/upload` | Multipart upload (`.zip` of a COCO/YOLO dataset) → registers the dataset, stores the artefact, records its SHA-256 |
| `POST` | `/dataset/analyze` | Runs the assurance pipeline via the AI engine, then stores results + contributor risks + evidence |
| `GET` | `/dataset/{id}` | Dataset with its latest stored analysis (results, risks, evidence) |
| `GET` | `/dataset/report/{id}` | Get-or-generate the assurance report for an analysis id (idempotent, SHA-256 stamped) |
| `GET` | `/dataset/evidence/{id}` | All stored evidence findings for an analysis id |

## Quick start

```bash
# 1. PostgreSQL with the trustvision DB (see docs/db/schema.sql + docs/ARCHITECTURE.md)
createdb trustvision

# 2. Start the AI engine (ai-engine/README.md) on :8100

# 3. Start this API (Flyway creates the module schema on boot)
mvn spring-boot:run
```

### Try it

```bash
# upload (multipart)
curl -X POST http://localhost:8080/dataset/upload \
  -F "file=@coco_dataset.zip" -F "name=Operation Aegis" \
  -F "codename=AEGIS-7" -F "format=COCO" -F "classification=OFFICIAL"

# analyse (synchronous: submits to the engine and stores the result)
curl -X POST http://localhost:8080/dataset/analyze \
  -H "Content-Type: application/json" \
  -d '{"datasetId": "<uuid>", "options": {"folds": 4}}'

# inspect / report / evidence
curl http://localhost:8080/dataset/<uuid>
curl http://localhost:8080/dataset/report/<analysisUuid>
curl http://localhost:8080/dataset/evidence/<analysisUuid>
```

## Layout

```
src/main/java/com/trustvision/dataset/
├── TrustVisionApplication.java
├── config/AppProperties.java        # app.storage / app.ai-engine / app.owner-username
├── controller/DatasetController.java
├── domain/                          # JPA entities (datasets, dataset_analysis, contributors,
│                                    #   contributor_risk, dataset_evidence, assurance_reports, users)
├── dto/
│   ├── request/AnalyzeRequest.java
│   ├── response/                    # ApiError, Dataset*, Evidence*, Report*, ComponentScoreDto
│   └── ai/AiEngineDtos.java         # snake_case mirror of the FastAPI engine contracts
├── exception/                       # ResourceNotFound / InvalidDataset / AiEngine + @RestControllerAdvice
├── repository/                      # Spring Data JPA repositories
├── service/                         # DatasetService, ReportService, AiEngineClient, StorageService
└── validation/DatasetFormat.java    # custom constraint (COCO | YOLO)
```

Schema is owned by Flyway: `src/main/resources/db/migration/V1__dataset_assurance.sql`
(native PostgreSQL enums + hash-format CHECKs, matching `docs/db/schema.sql`).
Hibernate runs with `ddl-auto: none`.

## Error model

`ApiError { timestamp, status, error, message, path, fieldErrors }` —
400 validation · 404 not found · 409 constraint conflict ·
413 upload too large · 422 invalid dataset operation ·
502 AI engine unreachable/failed · 500 fallback.

## Configuration (`application.yml`, env overrides)

| Key | Default | Purpose |
|-----|---------|---------|
| `app.storage.root` | `./workspace/storage` | artefact + report store |
| `app.ai-engine.base-url` | `http://localhost:8100` | FastAPI engine |
| `app.ai-engine.poll-interval` / `timeout` | `2s` / `15m` | job polling |
| `app.owner-username` | `system` | seeded actor (Flyway) |
