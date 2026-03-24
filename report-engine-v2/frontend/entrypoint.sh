#!/bin/sh
set -e

UI_USER="${UI_USER:-admin}"
UI_PASS="${UI_PASS:-SecretPassword@123}"
SSL_ENABLED="${SSL_ENABLED:-true}"

# Generate htpasswd from env vars
apk add --no-cache apache2-utils openssl > /dev/null 2>&1 || true
htpasswd -cb /etc/nginx/.htpasswd "$UI_USER" "$UI_PASS" 2>/dev/null
echo "Auth: $UI_USER / ****"

# Generate self-signed SSL cert if enabled and not mounted
if [ "$SSL_ENABLED" = "true" ]; then
  if [ ! -f /etc/nginx/ssl/selfsigned.crt ]; then
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
      -keyout /etc/nginx/ssl/selfsigned.key \
      -out /etc/nginx/ssl/selfsigned.crt \
      -subj "/CN=report-engine/O=Codesecure Solutions" 2>/dev/null
    echo "SSL: Self-signed certificate generated (10 year)"
  else
    echo "SSL: Using mounted certificate"
  fi
fi

# Write nginx config
if [ "$SSL_ENABLED" = "true" ]; then
cat > /etc/nginx/conf.d/default.conf << NGINX
# SSL only — no HTTP redirect
server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/selfsigned.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        auth_basic off;
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_connect_timeout 60s;
    }

    location / {
        auth_basic "Codesecure Report Engine";
        auth_basic_user_file /etc/nginx/.htpasswd;
        try_files \$uri \$uri/ /index.html;
    }
}

# HTTP (commented out — enable if needed)
# server {
#     listen 80;
#     server_name _;
#     root /usr/share/nginx/html;
#     index index.html;
#     location /api/ {
#         auth_basic off;
#         proxy_pass http://backend:8000/api/;
#         proxy_set_header Host \$host;
#         proxy_set_header X-Real-IP \$remote_addr;
#         proxy_read_timeout 600s;
#         proxy_send_timeout 600s;
#     }
#     location / {
#         auth_basic "Codesecure Report Engine";
#         auth_basic_user_file /etc/nginx/.htpasswd;
#         try_files \$uri \$uri/ /index.html;
#     }
# }
NGINX
echo "Nginx: HTTPS only on 443"
else
cat > /etc/nginx/conf.d/default.conf << NGINX
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        auth_basic off;
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_connect_timeout 60s;
    }

    location / {
        auth_basic "Codesecure Report Engine";
        auth_basic_user_file /etc/nginx/.htpasswd;
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX
echo "Nginx: HTTP only on 80"
fi

echo "Starting nginx..."
exec nginx -g "daemon off;"
