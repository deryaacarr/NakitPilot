#!/bin/sh
set -e

python - <<'PY'
import os
import socket
import sys
import time
from urllib.parse import urlparse

host = os.environ.get("POSTGRES_HOST")
port = int(os.environ.get("POSTGRES_PORT", "5432"))

if not host:
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        host = parsed.hostname or "postgres"
        port = parsed.port or 5432
    else:
        host = "postgres"

print(f"Waiting for PostgreSQL at {host}:{port}...")
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=1):
            print("PostgreSQL is up.")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print("Timed out waiting for PostgreSQL.", file=sys.stderr)
sys.exit(1)
PY

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput
fi

if [ "${COLLECTSTATIC:-0}" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
