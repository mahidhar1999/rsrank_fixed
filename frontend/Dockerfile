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
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;
    # Proxy /api calls to backend
    location /api/ {
        #proxy_pass https://rsrankfixed-production.up.railway.app;
        proxy_pass ${BACKEND_URL};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    
        proxy_set_header Host rsrankfixed-production.up.railway.app;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    
        proxy_ssl_server_name on;
    
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
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
