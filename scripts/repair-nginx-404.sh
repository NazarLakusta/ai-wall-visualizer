#!/usr/bin/env bash
# Run on Hetzner server: bash /opt/ai-wall-visualizer/scripts/repair-nginx-404.sh
set -euo pipefail
cd /opt/ai-wall-visualizer

echo "=== 1. Files on disk ==="
ls -la platform-admin/index.html admin/index.html mini-app/index.html

echo "=== 2. What listens on port 80 ==="
ss -tlnp | grep ':80' || true

echo "=== 3. Write nginx.conf ==="
cat > nginx/nginx.conf <<'EOF'
worker_processes auto;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    client_max_body_size 25M;
    resolver 127.0.0.11 valid=10s ipv6=off;
    server {
        listen 80 default_server;
        listen [::]:80 default_server;
        server_name _;
        location /api/ {
            set $api_upstream api:8000;
            proxy_pass http://$api_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        location = /app { return 301 /app/; }
        location /app/ {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /app/index.html;
        }
        location = /admin { return 301 /admin/; }
        location /admin/ {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /admin/index.html;
        }
        location = /platform { return 301 /platform/; }
        location /platform/ {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /platform/index.html;
        }
        location = / { return 302 /platform/; }
        location /health {
            set $api_upstream api:8000;
            proxy_pass http://$api_upstream/health;
        }
    }
}
EOF

echo "=== 4. Restart nginx ==="
docker compose up -d --force-recreate nginx
sleep 3

echo "=== 5. Files inside container ==="
docker compose exec nginx ls -la /usr/share/nginx/html/platform/ | head -5

echo "=== 6. Tests ==="
echo -n "127.0.0.1: "
curl -sI http://127.0.0.1/platform/ | head -1
echo -n "public IP:  "
curl -sI http://49.13.8.211/platform/ | head -1
