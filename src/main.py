"""InkVault API.

Run locally:  uv run uvicorn src.main:app --reload
Deploy:       Lambda handler via Mangum
API docs:     http://localhost:8000/docs
"""

from fastapi import FastAPI
from mangum import Mangum

from src.api.routes import router

app = FastAPI(
    title="InkVault",
    description="AI-powered document processing pipeline",
    version="0.1.0",
)

app.include_router(router)

# Lambda handler: Mangum wraps FastAPI for API Gateway
handler = Mangum(app, lifespan="off")
