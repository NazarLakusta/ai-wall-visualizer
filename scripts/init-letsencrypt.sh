#!/usr/bin/env bash
# Obtain Let's Encrypt cert, then switch to HTTPS prod nginx.
# Usage: DOMAIN=paint.example.com EMAIL=you@mail.com ./scripts/init-letsencrypt.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DOMAIN="${DOMAIN:?Set DOMAIN=paint.example.com}"
EMAIL="${EMAIL:?Set EMAIL=your@email.com}"

mkdir -p certbot/conf certbot/www

# Render prod nginx with real domain
sed "s/example/${DOMAIN}/g" nginx/nginx.prod.conf > nginx/nginx.prod.rendered.conf

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml"

echo "==> Starting stack (HTTP only) for certbot..."
$COMPOSE up -d --build postgres redis api worker bot cleanup ops

# Temporary nginx for ACME + health
docker run -d --name wallviz-nginx-bootstrap \
  --network "$(basename "$ROOT")_default" \
  -p 80:80 \
  -v "$ROOT/nginx/nginx.bootstrap.conf:/etc/nginx/nginx.conf:ro" \
  -v "$ROOT/certbot/www:/var/www/certbot:ro" \
  -v "$ROOT/mini-app:/usr/share/nginx/html/app:ro" \
  -v "$ROOT/admin:/usr/share/nginx/html/admin:ro" \
  -v "$ROOT/platform-admin:/usr/share/nginx/html/platform:ro" \
  nginx:alpine

echo "==> Requesting certificate for $DOMAIN ..."
docker run --rm \
  -v "$ROOT/certbot/conf:/etc/letsencrypt" \
  -v "$ROOT/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --non-interactive

docker rm -f wallviz-nginx-bootstrap

echo "==> Starting production stack with HTTPS..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build nginx

# Use rendered nginx config
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop nginx
docker run -d --name wallviz-nginx-prod \
  --network "$(basename "$ROOT")_default" \
  -p 80:80 -p 443:443 \
  -v "$ROOT/nginx/nginx.prod.rendered.conf:/etc/nginx/nginx.conf:ro" \
  -v "$ROOT/certbot/conf:/etc/letsencrypt:ro" \
  -v "$ROOT/certbot/www:/var/www/certbot:ro" \
  -v "$ROOT/mini-app:/usr/share/nginx/html/app:ro" \
  -v "$ROOT/admin:/usr/share/nginx/html/admin:ro" \
  -v "$ROOT/platform-admin:/usr/share/nginx/html/platform:ro" \
  --restart unless-stopped \
  nginx:alpine

echo "Done. Test: https://${DOMAIN}/health"
