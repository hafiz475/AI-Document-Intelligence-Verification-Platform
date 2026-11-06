FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install .

COPY apps/worker/src ./worker-src
ENV PYTHONPATH=/app/worker-src

CMD ["dramatiq", "assureai_worker.tasks"]
