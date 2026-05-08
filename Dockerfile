FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN python -m pip install --upgrade pip \
    && pip install --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CONCORD_DB_PATH=/app/data/concord.db

WORKDIR /app

RUN adduser --disabled-password --gecos "" concord \
    && mkdir -p /app/data \
    && chown -R concord:concord /app

COPY --from=builder /install /usr/local
COPY --from=builder /app/api /app/api
COPY --from=builder /app/graph /app/graph
COPY --from=builder /app/public /app/public
COPY --from=builder /app/shared /app/shared
COPY --from=builder /app/zone_a /app/zone_a
COPY --from=builder /app/zone_b /app/zone_b
COPY --from=builder /app/run_all.py /app/run_all.py

USER concord

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.index:app --host 0.0.0.0 --port ${PORT:-8000}"]
