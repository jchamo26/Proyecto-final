# SSL listo para Digital Ocean

Este documento deja listo el flujo de SSL para desplegar el proyecto en Digital Ocean usando Docker Compose y Nginx.

## 1. Requisitos previos

- Droplet Ubuntu con Docker y Docker Compose instalados
- Dominio con DNS apuntando al droplet
- Puerto 80 y 443 abiertos en el firewall de Digital Ocean
- Cuenta con acceso sudo

## 2. Clonar el proyecto

```bash
cd /opt
sudo mkdir -p clinico
sudo chown $USER:$USER clinico
cd clinico
git clone https://github.com/TU_USUARIO/TU_REPO.git .
```

## 3. Construir el frontend

```bash
cd /opt/clinico/frontend
npm install
npm run build
```

## 4. Preparar el archivo `.env`

```bash
cp .env.example .env
nano .env
```

Ajusta al menos:

```env
APP_ENV=production
REQUIRE_HTTPS=true
SECRET_KEY=<clave_secreta_segura>
FERNET_KEY=<clave_fernet_segura>
FRONTEND_HOST=https://TU_DOMINIO
ALLOWED_ORIGINS=https://TU_DOMINIO
DATABASE_URL=postgresql://clinico_user:<password>@postgres:5432/clinico_db
POSTGRES_PASSWORD=<password_seguro>
MINIO_ROOT_PASSWORD=<password_seguro>
```

## 5. Asegurar la configuración de Nginx

La configuración de Nginx en `nginx/conf.d/default.conf` ya está preparada para servir HTTPS en un dominio real.
Si quieres usar un dominio concreto, deja `server_name _;` para que el proxy sirva en la IP pública, o sustituye el valor por tu dominio si quieres una regla específica.

## 6. Generar certificado con Certbot

```bash
sudo apt-get update
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d TU_DOMINIO -d www.TU_DOMINIO --agree-tos --email admin@TU_DOMINIO
```

## 7. Copiar certificados al volumen del proxy

```bash
mkdir -p /opt/clinico/nginx/certs
sudo cp /etc/letsencrypt/live/TU_DOMINIO/fullchain.pem /opt/clinico/nginx/certs/fullchain.pem
sudo cp /etc/letsencrypt/live/TU_DOMINIO/privkey.pem /opt/clinico/nginx/certs/privkey.pem
sudo chmod 600 /opt/clinico/nginx/certs/privkey.pem
```

## 8. Levantar la arquitectura

```bash
cd /opt/clinico
docker compose up -d --build
docker compose ps
```

## 9. Verificación de HTTPS

```bash
curl -I https://TU_DOMINIO
openssl s_client -connect TU_DOMINIO:443 -servername TU_DOMINIO | openssl x509 -noout -dates
```

## 10. Renovación automática

```bash
sudo crontab -e
```

Agrega esta línea:

```cron
0 3 * * * certbot renew --quiet && cp /etc/letsencrypt/live/TU_DOMINIO/fullchain.pem /opt/clinico/nginx/certs/fullchain.pem && cp /etc/letsencrypt/live/TU_DOMINIO/privkey.pem /opt/clinico/nginx/certs/privkey.pem && docker compose -f /opt/clinico/docker-compose.yml restart nginx
```

## 11. Verificación pública

```bash
python scripts/verify_public_deployment.py https://TU_DOMINIO
```
