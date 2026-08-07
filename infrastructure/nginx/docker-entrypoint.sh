#!/bin/sh
# Generate self-signed TLS certs when none are mounted (local/prod bootstrap).
set -e

CERT_DIR=/etc/nginx/certs
CRT="$CERT_DIR/fullchain.pem"
KEY="$CERT_DIR/privkey.pem"

if [ ! -f "$CRT" ] || [ ! -f "$KEY" ]; then
  echo "NP-181: generating self-signed TLS certificate in $CERT_DIR"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$KEY" \
    -out "$CRT" \
    -subj "/CN=${TLS_CN:-localhost}"
fi

exec "$@"
