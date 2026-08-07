# Docker / Nginx / Observability (NP-180–185)

## Development

Stack = **7 services**: `postgres`, `redis`, `api`, `celery_worker`, `celery_beat`, `web`, `nginx`.

`docker compose up` may print `Running 12/12` — that count also includes **image builds** and the **network**, not 12 long-running services.

```bash
# Prefer these (repo root) — up starts all 7; down stops/removes all of them
make up
make down

# Equivalent
docker compose up -d --build --remove-orphans
docker compose down --remove-orphans
```

`make down` / `docker compose down` stops **every** project container and removes the network. Volumes (`postgres_data`, `web_node_modules`) are kept so data survives restarts. To wipe DB volumes too: `docker compose down -v` (destructive).

Uses Dockerfile targets `development` (hot reload, bind mounts).

## Production

```bash
# Ensure .env has SECRET_KEY, JWT_SIGNING_KEY, POSTGRES_PASSWORD, DEBUG=false
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

### NP-180 — production images

| Requirement | Implementation |
|-------------|----------------|
| Multi-stage build | `builder` / `development` / `production` stages |
| Non-root | API `nakitpilot`; Web `node` |
| Static files | `collectstatic` + nginx `/static/` + WhiteNoise |
| Health / restart / limits | Compose + Dockerfile |

### NP-181 — Nginx

- Image: `infrastructure/nginx/Dockerfile` (`fholzer/nginx-brotli`)
- HTTPS (443) + HTTP→HTTPS redirect (health stays on :80)
- API / frontend proxies, `client_max_body_size 25m`
- Security headers (HSTS, nosniff, frame-deny, CSP, …)
- Gzip + Brotli
- Rate limits: auth `5r/s`, API `20r/s`, imports `2r/s`
- Self-signed TLS bootstrap if certs volume empty (`TLS_CN`)

### NP-183 — Sentry

- Backend: `config/sentry.py` (Django + Celery + Redis), `before_send` scrubbing
- Frontend: `@sentry/nextjs` + AuthGuard sets `user.id` / `organization_id` (no email)
- Set `SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_RELEASE`

### NP-184 — Health

- `GET /api/health/live` — process up
- `GET /api/health/ready` — Postgres + Redis + storage
- Legacy `GET /health/` → readiness

### NP-185 — Initial admin

```bash
INITIAL_ADMIN_EMAIL=admin@example.com INITIAL_ADMIN_PASSWORD='…' \
  python manage.py create_initial_admin --noinput
```

Password is never hardcoded; use env or interactive `getpass`.

### Files

- `infrastructure/nginx/` — production reverse proxy
- `docker-compose.prod.yml` — production stack
- `apps/api/config/sentry.py`, `apps/api/apps/health/`
- `apps/api/apps/accounts/management/commands/create_initial_admin.py`
