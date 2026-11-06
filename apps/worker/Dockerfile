FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install --upgrade pip && pip install .

COPY apps/worker/src ./worker-src
ENV PYTHONPATH=/app/worker-src

CMD ["dramatiq", "assureai_worker.tasks"]
