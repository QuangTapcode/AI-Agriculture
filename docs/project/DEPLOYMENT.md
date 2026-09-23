# 🚀 Hướng dẫn Deployment

## Development Environment

### Yêu cầu
- Docker & Docker Compose
- Git

### Khởi động
```bash
docker-compose up -d
```

## Production Deployment

### 1. Chuẩn bị Server
- Ubuntu 20.04+ hoặc CentOS 7+
- Docker & Docker Compose
- Nginx (reverse proxy)
- SSL Certificate (Let's Encrypt)

### 2. Environment Variables

Tạo file `.env` với thông tin production:

```env
# Database
DATABASE_URL=postgresql://user:password@db:5432/agridb

# Redis
REDIS_URL=redis://redis:6379/0

# API Keys
CLAUDE_API_KEY=your_production_key
WEATHER_API_KEY=your_production_key

# Security
SECRET_KEY=your-very-secure-random-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
BACKEND_CORS_ORIGINS=["https://yourdomain.com"]

# Environment
ENVIRONMENT=production
```

### 3. Deploy với Docker Compose

```bash
# Pull latest code
git pull origin main

# Build và start services
docker-compose -f docker-compose.prod.yml up -d --build

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Frontend
    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5. Database Backup

```bash
# Backup
docker exec agridb pg_dump -U agriuser agridb > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i agridb psql -U agriuser agridb < backup_20240101.sql
```

### 6. Monitoring

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Resource usage
docker stats
```

## CI/CD với GitHub Actions

Tạo file `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /path/to/agri-ai
            git pull origin main
            docker-compose -f docker-compose.prod.yml up -d --build
```

## Scaling

### Horizontal Scaling
```yaml
# docker-compose.prod.yml
services:
  backend:
    deploy:
      replicas: 3
```

### Load Balancer
Sử dụng Nginx hoặc HAProxy để load balance giữa các backend instances.
