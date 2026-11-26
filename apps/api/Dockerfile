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

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install .

USER 10001:10001

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn assureai_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM runtime AS test

USER root

COPY tests ./tests
RUN pip install ".[dev]"
USER 10001:10001
CMD ["sh", "-c", "ruff check . && ruff format --check . && mypy src tests && pytest"]
