FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --upgrade pip && pip install .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn assureai_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM runtime AS test

COPY tests ./tests
RUN pip install ".[dev]"
CMD ["sh", "-c", "ruff check . && ruff format --check . && mypy src tests && pytest"]
