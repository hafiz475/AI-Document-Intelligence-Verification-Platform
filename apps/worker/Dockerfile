FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 10001 assureai && \
    adduser --system --uid 10001 --ingroup assureai assureai && \
    mkdir -p /data/documents && chown -R assureai:assureai /data

COPY apps/api/pyproject.toml ./
COPY apps/api/src ./src
RUN pip install .

COPY apps/worker/src ./worker-src
ENV PYTHONPATH=/app/worker-src
RUN chown -R assureai:assureai /app && chmod -R u=rwX,go=rX /app

USER 10001:10001

CMD ["dramatiq", "assureai_worker.tasks"]
