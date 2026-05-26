# Guía de Deployment - Sistema Clínico Inteligente

## 1. Preparación del Ambiente

### 1.1 Requisitos Previos

**Hardware Mínimo:**
- CPU: 2 cores
- RAM: 4GB
- Almacenamiento: 10GB SSD
- Conexión: Ancho de banda estable

**Software Requerido:**
- Python 3.12+ 
- Docker & Docker Compose (opcional pero recomendado)
- Git
- PostgreSQL 14+ (para producción)
- Redis 6.0+
- HAPI FHIR R4

### 1.2 Variables de Entorno Producción

```bash
# Seguridad
SECRET_KEY=<generar-con-secrets.token_urlsafe(32)>
FERNET_KEY=<generar-con-Fernet.generate_key()>

# Credenciales SuperUser
SUPERUSER_EMAIL=medico@produccion.com
SUPERUSER_PASSWORD=<contraseña-fuerte>
SUPERUSER_LICENSE=<número-licencia>

# Base de Datos
DATABASE_URL=postgresql://user:password@postgres.prod:5432/clinico_db

# Redis
REDIS_URL=redis://redis.prod:6379/0

# LLM & Servicios
LLM_ENDPOINT=http://llm.prod:8501
ML_SERVICE_URL=http://ml.prod:8100
DL_SERVICE_URL=http://dl.prod:8200
FHIR_SERVER_URL=http://fhir.prod:8080/hapi-fhir-jpaserver

# MLFlow
MLFLOW_TRACKING_URI=http://mlflow.prod:5000

# MinIO
MINIO_ROOT_USER=<usuario>
MINIO_ROOT_PASSWORD=<contraseña>
MINIO_ENDPOINT=s3.prod:9000

# Cloudflare
CLOUDFLARE_API_KEY=<api-key>
CLOUDFLARE_ZONE_ID=<zone-id>
CLOUDFLARE_EMAIL=admin@domain.com

# Frontend
FRONTEND_HOST=https://clinico.domain.com
```

## 2. Deployment con Docker Compose

### 2.1 Estructura de Producción

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: clinico_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: clinico_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - clinico_net
    restart: always

  # Redis Cache
  redis:
    image: redis:7-alpine
    networks:
      - clinico_net
    restart: always

  # Mock OpenAI Server (Desarrollo)
  mock-server:
    build:
      context: .
      dockerfile: Dockerfile.mock
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      MOCK_PORT: 8501
    ports:
      - "8501:8501"
    networks:
      - clinico_net
    restart: always

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://clinico_user:${DB_PASSWORD}@postgres:5432/clinico_db
      REDIS_URL: redis://redis:6379/0
      LLM_ENDPOINT: http://mock-server:8501
      SECRET_KEY: ${SECRET_KEY}
      FERNET_KEY: ${FERNET_KEY}
    ports:
      - "9000:9000"
    depends_on:
      - postgres
      - redis
      - mock-server
    networks:
      - clinico_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
    networks:
      - clinico_net
    restart: always

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      VITE_API_URL: http://backend:9000
    ports:
      - "3000:80"
    networks:
      - clinico_net
    restart: always

volumes:
  postgres_data:

networks:
  clinico_net:
    driver: bridge
```

### 2.2 Dockerfile para Backend

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9000/healthz')"

# Comando para iniciar
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
```

### 2.3 Configuración Nginx

```nginx
upstream backend {
    server backend:9000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name clinico.domain.com;
    
    # Redirigir a HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name clinico.domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    }
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # Health Check
    location /health {
        access_log off;
        return 200 "healthy";
    }
}
```

## 3. Deployment en VPS (Digital Ocean / AWS)

### 3.1 Preparación del Servidor

```bash
# Actualizar sistema
sudo apt-get update && sudo apt-get upgrade -y

# Instalar dependencias
sudo apt-get install -y \
    curl \
    wget \
    git \
    python3.12 \
    python3-pip \
    docker.io \
    docker-compose \
    postgresql \
    redis-server \
    nginx

# Crear usuario para aplicación
sudo useradd -m -s /bin/bash clinico
sudo usermod -aG docker clinico

# Crear directorio de aplicación
sudo mkdir -p /opt/clinico
sudo chown clinico:clinico /opt/clinico
```

### 3.2 Deployment con Docker Compose

```bash
# Clonar repositorio
cd /opt/clinico
git clone https://github.com/usuario/ProyectoFinal_SSD.git .

# Crear archivo .env
cp .env.example .env
nano .env  # Editar variables de producción

# Construir y levantar servicios
docker-compose -f docker-compose.prod.yml up -d --build

# Verificar estado
docker-compose ps
docker-compose logs -f backend
```

### 3.3 Certificados SSL con Let's Encrypt

```bash
# Instalar Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Generar certificado
sudo certbot certonly --standalone -d clinico.domain.com

# Renovación automática
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

## 4. Monitoreo y Mantenimiento

### 4.1 Healthchecks

```bash
# Ver estado de servicios
docker-compose ps

# Logs del backend
docker-compose logs -f backend

# Logs de Nginx
docker-compose logs -f nginx

# Monitor de recursos
docker stats
```

### 4.2 Backups

```bash
# Backup diario de base de datos
0 2 * * * sudo docker-compose exec -T postgres pg_dump -U clinico_user clinico_db | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz

# Verificar integridad
postgresql_bin/pg_dump --format=custom --compress=9 --dbname=postgresql://clinico_user:pass@localhost:5432/clinico_db --file=/backups/clinico_db.dump
```

### 4.3 Scaling

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    build: ./backend
    deploy:
      replicas: 3  # 3 instancias
      update_config:
        parallelism: 1
        delay: 10s
    # ... resto de configuración
```

## 5. Seguridad en Producción

### 5.1 Firewall

```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 5432/tcp # PostgreSQL (solo desde red interna)
```

### 5.2 HTTPS Obligatorio

```python
# backend/app/main.py
app.add_middleware(
    HTTPSRedirectMiddleware,
)
```

### 5.3 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 5.4 Secrets Management

```bash
# Usar secrets locales (no en código)
docker-compose config | grep -E "SECRET|PASSWORD|KEY"

# Verificar permisos de .env
chmod 600 .env
```

## 6. CI/CD Pipeline

### 6.1 GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build and Push Docker Image
        uses: docker/build-push-action@v2
        with:
          push: true
          tags: myregistry/clinico:latest
      
      - name: Deploy to VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_KEY }}
          script: |
            cd /opt/clinico
            docker-compose pull
            docker-compose up -d
```

## 7. Troubleshooting

### Puerto en Uso
```bash
# Encontrar proceso
lsof -i :9000

# Matar proceso
kill -9 <PID>
```

### Base de Datos No Conecta
```bash
# Verificar conexión
psql -U clinico_user -d clinico_db -h postgres -c "SELECT 1"
```

### Logs Llenos
```bash
# Limpiar logs de Docker
docker system prune -a --volumes
```

## 8. Rollback

```bash
# Ver versiones anteriores
docker-compose ps --services

# Revertir a versión anterior
git checkout <commit-hash>
docker-compose up -d --build
```

## Checklist de Deployment

- [ ] Variables de entorno configuradas
- [ ] SSL/TLS instalado y verificado
- [ ] Backups automáticos configurados
- [ ] Monitoreo y alertas activos
- [ ] Logs centralizados
- [ ] Health checks pasando
- [ ] Performance tests completados
- [ ] Seguridad auditada
- [ ] Documentación actualizada
- [ ] Plan de rollback definido

---

**Versión:** 1.0  
**Última actualización:** Mayo 18, 2026  
**Estado:** ✓ Operacional
