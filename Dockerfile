FROM python:3.13-slim

WORKDIR /app

# system deps for weasyprint and tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev libcairo2 tesseract-ocr tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

COPY src/ ./src/
COPY classifier/ ./classifier/
COPY migrations/ ./migrations/
COPY alembic.ini ./

EXPOSE 8000
CMD ["sh", "-c", "uv run python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
