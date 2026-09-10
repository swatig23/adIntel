# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY src ./src

# Cloud Run injects $PORT at runtime (defaults to 8080 locally)
ENV PORT=8080
EXPOSE 8080

# Shell form so $PORT expands correctly
CMD uv run uvicorn adintel.main:app --host 0.0.0.0 --port ${PORT}
