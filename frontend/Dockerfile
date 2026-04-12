FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# ── Production nginx stage ──────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config for React Router (SPA)
RUN mkdir -p /etc/nginx/templates && cat > /etc/nginx/templates/default.conf.template << 'EOF'
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # Proxy /api calls to backend
    location /api/ {
        proxy_pass https://rsrankfixed-production.up.railway.app/api/;
        proxy_ssl_server_name on;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # All other routes → index.html (React Router)
    location / {
        try_files $uri $uri/ /index.html;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
EOF

EXPOSE 80
