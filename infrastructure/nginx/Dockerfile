# NP-181 — nginx with Brotli (fholzer) + TLS bootstrap
FROM fholzer/nginx-brotli:v1.28.0

# OpenSSL for self-signed bootstrap when certs are not mounted
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/certs /var/www/static /var/www/certbot

COPY 00-http-tuning.conf /etc/nginx/conf.d/00-http-tuning.conf
COPY production.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint-nakitpilot.sh

RUN chmod +x /docker-entrypoint-nakitpilot.sh

EXPOSE 80 443

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1/api/health/live || wget -qO- http://127.0.0.1/health/ || exit 1

ENTRYPOINT ["/docker-entrypoint-nakitpilot.sh"]
CMD ["nginx", "-g", "daemon off;"]
