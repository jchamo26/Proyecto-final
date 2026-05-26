# Análisis y Fixes del Backend

## 1. Problemas Identificados

### 1.1 Problemas Históricos

**Problema 1: Exit Code 1 al iniciar uvicorn**
- **Síntoma**: El backend falla inmediatamente al iniciarse
- **Causa Raíz**: Generalmente es import errors o missing dependencies
- **Solución**: Ver sección 2 abajo

**Problema 2: "Secret key not set"**
- **Síntoma**: Error al iniciar debido a SECRET_KEY faltante
- **Causa**: Variable de entorno no configurada
- **Solución**: Exportar SECRET_KEY antes de iniciar

**Problema 3: Port already in use**
- **Síntoma**: "Address already in use" en puerto 9000
- **Causa**: Instancia anterior del backend sigue corriendo
- **Solución**: Matar proceso anterior o cambiar puerto

**Problema 4: Database lock**
- **Síntoma**: "database is locked" en SQLite
- **Causa**: Múltiples procesos accediendo a database
- **Solución**: Usar PostgreSQL para producción

## 2. Diagnóstico y Fixes

### 2.1 Ejecutar Diagnóstico

```bash
python scripts/backend_diagnostics.py
```

Genera reporte completo en `backend_diagnostic_report.json`

### 2.2 Checks Automáticos

El script verifica:
- ✓ Versión de Python (3.12+)
- ✓ Dependencias instaladas
- ✓ Variables de entorno
- ✓ Estructura de directorios
- ✓ Imports funcionan
- ✓ FastAPI app se crea
- ✓ Conexión a mock server
- ✓ Configuración de BD
- ✓ Permisos de archivos
- ✓ Sintaxis de Python

## 3. Soluciones Específicas

### 3.1 ImportError: No module named 'app'

**Causa**: PYTHONPATH no incluye el directorio backend

**Solución:**
```bash
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn app.main:app --host 127.0.0.1 --port 9000
```

O usar el startup script:
```bash
python start_system.py
```

### 3.2 ModuleNotFoundError: No module named 'pydantic'

**Causa**: Dependencias no instaladas

**Solución:**
```bash
cd backend
pip install -r requirements.txt
```

### 3.3 fastapi not found

**Causa**: FastAPI no está instalado

**Solución:**
```bash
pip install fastapi uvicorn sqlalchemy pydantic openai ragas datasets
```

### 3.4 KeyError: 'SECRET_KEY'

**Causa**: Variable de entorno no set

**Solución - Linux/Mac:**
```bash
export SECRET_KEY="test-secret-key-$(openssl rand -hex 32)"
export FERNET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
python start_system.py
```

**Solución - Windows PowerShell:**
```powershell
$env:SECRET_KEY = "test-secret-key"
$env:FERNET_KEY = "R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="
python start_system.py
```

### 3.5 Address already in use (Port 9000)

**Causa**: Puerto está en uso

**Solución:**
```bash
# Encontrar proceso
lsof -i :9000  # macOS/Linux
netstat -ano | findstr :9000  # Windows

# Matar proceso
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

O cambiar puerto:
```bash
uvicorn app.main:app --port 9001
```

### 3.6 database is locked (SQLite)

**Causa**: Múltiples procesos accediendo SQLite simultáneamente

**Solución - Temporal:**
```bash
# Usar PostgreSQL en lugar de SQLite
export DATABASE_URL="postgresql://user:pass@localhost/clinico"
```

**Solución - Definitiva:**
```yaml
# docker-compose.yml
postgres:
  image: postgres:14-alpine
  environment:
    POSTGRES_DB: clinico_db
    POSTGRES_USER: clinico_user
    POSTGRES_PASSWORD: securepass
```

## 4. Checklist de Startup

Antes de iniciar backend, asegúrate de:

### Pre-requisitos

- [ ] Python 3.12+ instalado: `python --version`
- [ ] Dependencias instaladas: `pip list | grep fastapi`
- [ ] Mock server corriendo: `curl http://127.0.0.1:8501/health`
- [ ] Directorio correcto: `pwd` debe ser raíz del proyecto
- [ ] Puerto 9000 disponible: `lsof -i :9000`

### Variables de Entorno

```bash
# Verificar que están set
env | grep SECRET_KEY
env | grep FERNET_KEY
env | grep OPENAI_API_KEY
env | grep LLM_ENDPOINT
```

Si faltan:
```bash
export SECRET_KEY="test-secret"
export FERNET_KEY="R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="
export OPENAI_API_KEY="local_dummy_key"
export LLM_ENDPOINT="http://127.0.0.1:8501"
```

### Archivo .env (Alternativa)

Crear `backend/.env`:
```
SECRET_KEY=test-secret-key-change-in-production
FERNET_KEY=R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc=
OPENAI_API_KEY=local_dummy_key
LLM_ENDPOINT=http://127.0.0.1:8501
DATABASE_URL=sqlite:///./test.db
ACCESS_TOKEN_EXPIRE_MINUTES=60
SUPERUSER_EMAIL=medico@example.com
SUPERUSER_PASSWORD=SuperPass2026
SUPERUSER_LICENSE=MED123456
```

Luego cargar en el código:
```python
from dotenv import load_dotenv
load_dotenv()
```

## 5. Flujo de Startup Correcto

### Opción 1: Usar start_system.py (Recomendado)

```bash
python start_system.py
# O:
python start_system.ps1  # En Windows PowerShell
```

**Ventajas:**
- ✓ Configura variables automáticamente
- ✓ Inicia mock server antes que backend
- ✓ Logging centralizado
- ✓ Manejo de señales SIGINT

### Opción 2: Manual (Para debugging)

```bash
# Terminal 1: Mock Server
python scripts/mock_openai_server.py

# Terminal 2: Backend
cd backend
export SECRET_KEY="test-secret"
export FERNET_KEY="R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="
uvicorn app.main:app --host 127.0.0.1 --port 9000 --log-level debug

# Terminal 3: Test
curl http://127.0.0.1:9000/docs
```

### Opción 3: Docker (Producción)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 6. Verificación Post-Startup

### 6.1 Backend está corriendo

```bash
curl http://127.0.0.1:9000/healthz
# Response: OK
```

### 6.2 API Docs disponible

```bash
# Abrir en navegador
http://localhost:9000/docs
```

### 6.3 RAGAS endpoints funcionan

```bash
curl http://127.0.0.1:9000/api/v1/ragas/health
# Response: {"service": "ragas_integration", "available": true}
```

### 6.4 Mock server integrado

```bash
curl http://127.0.0.1:9000/api/v1/ragas/status
# Response: {"status": "healthy", "mock_server": true}
```

## 7. Troubleshooting Avanzado

### Ver logs detallados

```bash
# Iniciar con log-level debug
uvicorn app.main:app --log-level debug

# O ver logs después
tail -f startup.log
```

### Ver requests/responses

```python
# En app/main.py, agregar:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Debuggear con pdb

```python
# Agregar en app/main.py
import pdb; pdb.set_trace()

# O usar el debugger de VS Code
# Crear .vscode/launch.json
```

### Testing de endpoints

```bash
# Con httpie (más legible que curl)
pip install httpie

http POST http://127.0.0.1:9000/api/v1/ragas/evaluate \
  user_input="¿Cuál es el riesgo?" \
  response="Riesgo alto" \
  retrieved_contexts:='["contexto1"]'
```

## 8. Monitoreo Continuo

### Script de Health Check

```bash
#!/bin/bash
while true; do
  curl -s http://127.0.0.1:9000/healthz | grep -q OK
  if [ $? -eq 0 ]; then
    echo "✓ Backend OK"
  else
    echo "✗ Backend DOWN"
  fi
  sleep 10
done
```

### Alertas en tiempo real

```python
# healthcheck_monitor.py
import requests
import time

url = "http://127.0.0.1:9000/healthz"
while True:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            print("⚠ Backend returned non-200")
    except Exception as e:
        print(f"✗ Backend DOWN: {e}")
    time.sleep(10)
```

## 9. Optimizaciones de Performance

Ver `docs/OPTIMIZATION.md` para:
- Caching de embeddings
- Connection pooling
- Batch processing
- Response compression

## 10. Referencias

- FastAPI docs: https://fastapi.tiangolo.com/
- Uvicorn docs: https://www.uvicorn.org/
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- Pydantic docs: https://docs.pydantic.dev/

---

## Anexo: Environment Variables Reference

```bash
# Core
SECRET_KEY              # Clave secreta (generar con secrets.token_urlsafe(32))
FERNET_KEY              # Clave de encriptación (generar con Fernet.generate_key())
OPENAI_API_KEY          # API key para OpenAI (local_dummy_key para mock)
LLM_ENDPOINT            # URL del LLM (http://127.0.0.1:8501 para mock)

# Database
DATABASE_URL            # postgresql:// o sqlite:///
SQLALCHEMY_ECHO         # true/false - mostrar queries SQL

# Auth
ACCESS_TOKEN_EXPIRE_MINUTES  # Expiración de tokens (60)
SUPERUSER_EMAIL         # Email del superuser
SUPERUSER_PASSWORD      # Password del superuser
SUPERUSER_LICENSE       # Número de licencia

# Services
MLFLOW_TRACKING_URI     # http://localhost:5000
REDIS_URL               # redis://localhost:6379/0
MINIO_ROOT_USER         # minioadmin
MINIO_ROOT_PASSWORD     # minioadmin

# Other
FRONTEND_HOST           # http://localhost
FHIR_SERVER_URL         # http://localhost:8080/hapi-fhir-jpaserver
ML_SERVICE_URL          # http://localhost:8100
DL_SERVICE_URL          # http://localhost:8200
```

---

**Versión:** 1.0  
**Última actualización:** Mayo 18, 2026  
**Estado:** ✓ Production Ready
