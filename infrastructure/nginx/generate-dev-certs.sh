#!/usr/bin/env sh
# Generate self-signed certs for local HTTPS testing (NP-181).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$ROOT/certs}"
mkdir -p "$OUT"
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$OUT/privkey.pem" \
  -out "$OUT/fullchain.pem" \
  -subj "/CN=${TLS_CN:-localhost}"
echo "Wrote $OUT/fullchain.pem and $OUT/privkey.pem"
