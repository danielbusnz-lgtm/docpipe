# InkVault

Document processing pipeline that classifies PDFs, extracts structured data with AWS Bedrock (Claude), validates the output, and stores everything across S3, DynamoDB, and PostgreSQL. Exposed via FastAPI, deployed to Lambda with CDK.

## Architecture

```
                         ┌─────────────────┐
                         │   API Gateway    │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  Lambda (API)    │
                         │  FastAPI/Mangum  │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                    │
     ┌────────▼───────┐ ┌────────▼────────┐ ┌────────▼────────┐
     │       S3       │ │    DynamoDB     │ │   PostgreSQL    │
     │  raw PDFs      │ │  metadata +     │ │  structured     │
     │                │ │  status         │ │  extractions    │
     └────────┬───────┘ └─────────────────┘ └─────────────────┘
              │
     ┌────────▼────────┐
     │ Lambda (Process) │
     │  S3 trigger      │
     └────────┬─────────┘
              │
   ┌──────────▼──────────┐
   │   Processing Pipeline│
   │                      │
   │  1. Classify (TF-IDF)│
   │  2. Extract (Bedrock)│
   │  3. Validate         │
   │  4. Store            │
   └──────────────────────┘
```

**Upload flow**: Client uploads PDF via API. S3 stores the raw file, DynamoDB tracks status, and a background task (or S3 trigger Lambda) runs the processing pipeline.

**Processing pipeline**: The classifier (TF-IDF + LogisticRegression) determines the document type. Bedrock Claude extracts structured data using the Converse API with JSON schema enforcement. A validator checks math (line item totals, tax calculations) and required fields. Results go to PostgreSQL.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Mangum (Lambda adapter) |
| AI/ML | AWS Bedrock (Claude), scikit-learn |
| Storage | S3, DynamoDB, PostgreSQL + SQLAlchemy 2.0 |
| Infrastructure | AWS CDK (Python), Docker |
| Training | WeasyPrint, Faker, Tesseract OCR, MLflow |

## Project Structure

```
src/
  api/
    routes.py          # REST endpoints
    deps.py            # FastAPI dependency injection
  db/
    session.py         # SQLAlchemy engine + session
    dynamo.py          # DynamoDB CRUD
  models/
    domain.py          # Pydantic extraction models
    schemas.py         # API response shapes
    database.py        # SQLAlchemy ORM tables
  services/
    classifier.py      # TF-IDF document classification
    extractor.py       # Bedrock Claude structured extraction
    validator.py       # Math and field validation
    storage.py         # Write extractions to Postgres
    s3.py              # S3 file operations
  pipeline/
    processor.py       # Orchestrates classify > extract > validate > store
  config.py            # Settings from environment variables
  main.py              # FastAPI app + Lambda handler

scripts/
  generate_training_data.py   # Parallel synthetic PDF generation
  train_classifier.py         # MLflow training with GridSearchCV
  providers/                  # Faker providers (invoice, receipt, contract, other)
  templates/                  # Jinja2 HTML templates for PDF rendering

classifier/                   # Trained model artifacts + vocab
infra/                        # AWS CDK stack definitions
migrations/                   # Alembic database migrations
tests/                        # 108 tests
```

## API Endpoints

All routes are under `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/documents` | Upload a PDF. Returns document_id, starts processing in background. |
| `GET` | `/documents` | List documents. Optional `?status=` filter. |
| `GET` | `/documents/{id}` | Full document detail with classification and extraction status. |
| `GET` | `/documents/{id}/download` | Presigned S3 download URL for the original PDF. |
| `DELETE` | `/documents/{id}` | Delete document metadata. |
| `GET` | `/health` | Connectivity check for Postgres, DynamoDB, and S3. |

## Classifier

The document classifier is a scikit-learn Pipeline (TF-IDF + LogisticRegression) trained on synthetic PDFs generated with Faker + WeasyPrint, augmented with real documents from Kaggle.

Training data generation supports parallel rendering with `ProcessPoolExecutor` and optional OCR augmentation via Tesseract to simulate scanned documents. The training script runs GridSearchCV across 12 hyperparameter combinations, tracks everything in MLflow, and produces evaluation plots (confusion matrix, confidence histograms, calibration curves, ROC, precision/recall, classification report heatmap).

### Generate training data

```bash
uv run python scripts/generate_training_data.py --per-class 2500 --ocr-ratio 0.15
```

### Train the model

```bash
uv run python scripts/train_classifier.py
```

Model artifacts land in `classifier/` and get registered in MLflow.

## Local Development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker (for Postgres and LocalStack)
- Tesseract OCR (`sudo apt install tesseract-ocr`)
- poppler-utils (`sudo apt install poppler-utils`)

### Setup

```bash
# install dependencies
uv sync

# start Postgres and LocalStack
docker compose up -d

# run database migrations
uv run alembic upgrade head

# create LocalStack resources
aws --endpoint-url=http://localhost:4566 s3 mb s3://inkvault-documents
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
  --table-name inkvault-metadata \
  --attribute-definitions AttributeName=document_id,AttributeType=S \
  --key-schema AttributeName=document_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# start the API
uv run uvicorn src.main:app --reload
```

API docs at http://localhost:8000/docs.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `INKVAULT_S3_BUCKET` | `inkvault-documents` | S3 bucket name |
| `INKVAULT_DYNAMO_TABLE` | `inkvault-metadata` | DynamoDB table name |
| `INKVAULT_PG_URL` | `postgresql://inkvault:inkvault@localhost:5432/inkvault` | PostgreSQL connection string |
| `INKVAULT_BEDROCK_MODEL` | `anthropic.claude-sonnet-4-20250514` | Bedrock model ID |
| `INKVAULT_S3_ENDPOINT` | None | LocalStack S3 endpoint |
| `INKVAULT_DYNAMO_ENDPOINT` | None | LocalStack DynamoDB endpoint |
| `LOG_LEVEL` | `INFO` | Logging level |

## Deploy to AWS

Infrastructure is defined in CDK (Python). The stack creates:
- S3 bucket for document storage
- DynamoDB table with a `status-created_at` GSI
- Two Lambda functions (API handler + S3 trigger processor)
- API Gateway (proxy mode, routes everything to FastAPI)
- IAM policies for Bedrock, S3, and DynamoDB access

```bash
cd infra
pip install -r requirements.txt
cdk bootstrap   # first time only
cdk deploy
```

## Tests

```bash
# all tests (requires Docker for Postgres integration tests)
docker compose up -d
uv run pytest

# just unit tests
uv run pytest tests/ -k "not storage"

# specific test file
uv run pytest tests/test_extractor.py -v
```

108 tests covering providers, PDF rendering, data quality, extraction, validation, storage, and pipeline orchestration.
