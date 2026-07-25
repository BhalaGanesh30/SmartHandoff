# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Cloud Run: PORT env var injected at runtime (default 8080)
ENV PORT=8080

# Non-root user (SEC — least privilege)
RUN adduser --disabled-password --gecos "" appuser
USER appuser

CMD ["python", "-m", "app.main"]
