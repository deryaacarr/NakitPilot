# syntax=docker/dockerfile:1
# NP-180 — multi-stage API image (development + production targets)

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Builder — install Python deps into an isolated prefix
# ---------------------------------------------------------------------------
FROM base AS builder

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Development — hot-reload friendly (used by docker-compose.yml)
# ---------------------------------------------------------------------------
FROM base AS development

COPY --from=builder /install /usr/local
COPY . .
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------------------------------------------------------------------------
# Production — non-root, gunicorn, baked collectstatic
# ---------------------------------------------------------------------------
FROM base AS production

RUN groupadd --system --gid 1000 nakitpilot \
    && useradd --system --uid 1000 --gid nakitpilot --home-dir /app --shell /usr/sbin/nologin nakitpilot \
    && mkdir -p /app/staticfiles /app/media /app/private_uploads \
    && chown -R nakitpilot:nakitpilot /app

COPY --from=builder /install /usr/local
COPY --chown=nakitpilot:nakitpilot . .

RUN chmod +x /app/docker/entrypoint.sh \
    && SECRET_KEY=build-only-not-for-runtime \
       DEBUG=0 \
       ALLOWED_HOSTS=localhost \
       DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build \
       python manage.py collectstatic --noinput

USER nakitpilot

ENV COLLECTSTATIC=0 \
    RUN_MIGRATIONS=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/health/ready/ || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "docker/gunicorn.conf.py"]
