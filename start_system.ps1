# Script de Startup para Windows PowerShell
# Sistema Clínico Inteligente - Proyecto Final SSD
# Inicia Mock Server + Backend de forma simplificada

param(
    [string]$Mode = "all",  # all, mock, backend, ragas
    [switch]$Interactive,
    [switch]$NoWait
)

$ErrorActionPreference = "SilentlyContinue"

# Variables globales
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommandPath
$ProcessLog = Join-Path $ScriptRoot "startup.log"
$ProcessIds = @{}

# Colores
$Colors = @{
    Success = "Green"
    Error   = "Red"
    Warning = "Yellow"
    Info    = "Cyan"
    Debug   = "DarkGray"
}

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("Info", "Success", "Error", "Warning", "Debug")]
        [string]$Level = "Info"
    )
    
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "[$Timestamp] [$($Level.ToUpper())] $Message"
    
    Write-Host $LogMessage -ForegroundColor $Colors[$Level]
    Add-Content -Path $ProcessLog -Value $LogMessage -Encoding UTF8
}

function Print-Banner {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                        ║" -ForegroundColor Cyan
    Write-Host "║     SISTEMA DE STARTUP - PROYECTO FINAL SSD           ║" -ForegroundColor Cyan
    Write-Host "║     Sistema Clínico Inteligente 2026                  ║" -ForegroundColor Cyan
    Write-Host "║                                                        ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Start-MockServer {
    Write-Log "Iniciando Mock OpenAI Server..." "Info"
    
    # Verificar que no esté corriendo
    $existing = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Log "Deteniendo instancia anterior en puerto 8501..." "Warning"
        $existing.OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 500
    }
    
    # Configurar variables de entorno
    $env:OPENAI_API_KEY = "local_dummy_key"
    $env:MOCK_LOG_LEVEL = "INFO"
    
    # Iniciar proceso
    $process = Start-Process -FilePath python `
        -ArgumentList "scripts\mock_openai_server.py" `
        -WorkingDirectory $ScriptRoot `
        -NoNewWindow `
        -PassThru
    
    $ProcessIds["mock_server"] = $process.Id
    Write-Log "✓ Mock Server iniciado (PID: $($process.Id), Puerto: 8501)" "Success"
    
    # Esperar a que se levante
    Start-Sleep -Seconds 2
    
    return $process
}

function Start-Backend {
    Write-Log "Iniciando FastAPI Backend..." "Info"
    
    # Configurar variables de entorno
    $env:SECRET_KEY = "testsecret123"
    $env:ACCESS_TOKEN_EXPIRE_MINUTES = "60"
    $env:SUPERUSER_EMAIL = "medico@example.com"
    $env:SUPERUSER_PASSWORD = "SuperPass2026"
    $env:SUPERUSER_LICENSE = "MED123456"
    $env:FERNET_KEY = "R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc="
    $env:MLFLOW_TRACKING_URI = "http://localhost:5000"
    $env:REDIS_URL = "redis://localhost:6379/0"
    $env:LLM_ENDPOINT = "http://127.0.0.1:8501"
    $env:ML_SERVICE_URL = "http://localhost:8100"
    $env:DL_SERVICE_URL = "http://localhost:8200"
    $env:FHIR_SERVER_URL = "http://localhost:8080/hapi-fhir-jpaserver"
    $env:FRONTEND_HOST = "http://localhost"
    $env:DATABASE_URL = "sqlite:///./test.db"
    $env:MINIO_ROOT_USER = "minioadmin"
    $env:MINIO_ROOT_PASSWORD = "minioadmin"
    
    # Verificar que no esté corriendo
    $existing = Get-NetTCPConnection -LocalPort 9000 -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Log "Deteniendo instancia anterior en puerto 9000..." "Warning"
        $existing.OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 500
    }
    
    # Iniciar proceso
    $process = Start-Process -FilePath python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9000", "--log-level", "info" `
        -WorkingDirectory (Join-Path $ScriptRoot "backend") `
        -NoNewWindow `
        -PassThru
    
    $ProcessIds["backend"] = $process.Id
    Write-Log "✓ Backend iniciado (PID: $($process.Id), Puerto: 9000)" "Success"
    
    # Esperar a que se levante
    Start-Sleep -Seconds 3
    
    return $process
}

function Run-RAGAS {
    Write-Log "Ejecutando evaluación RAGAS..." "Info"
    
    $env:LLM_ENDPOINT = "http://127.0.0.1:8501"
    $env:OPENAI_API_KEY = "local_dummy_key"
    
    $process = Start-Process -FilePath python `
        -ArgumentList "notebooks\ragas_evaluation.py" `
        -WorkingDirectory $ScriptRoot `
        -NoNewWindow `
        -PassThru -Wait
    
    Write-Log "✓ RAGAS evaluation completada" "Success"
}

function Print-Status {
    Write-Host ""
    Write-Host "📊 ESTADO DE SERVICIOS:" -ForegroundColor Yellow
    Write-Host ""
    
    $services = @{
        "Mock Server"      = @{ Pid = $ProcessIds["mock_server"]; Port = 8501; URL = "http://127.0.0.1:8501" }
        "Backend API"      = @{ Pid = $ProcessIds["backend"]; Port = 9000; URL = "http://127.0.0.1:9000" }
    }
    
    foreach ($service in $services.GetEnumerator()) {
        if ($service.Value.Pid) {
            $proc = Get-Process -Id $service.Value.Pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  🟢 $($service.Key)" -ForegroundColor Green
                Write-Host "     Puerto: $($service.Value.Port) | URL: $($service.Value.URL)" -ForegroundColor DarkGray
            }
        }
    }
    
    Write-Host ""
    Write-Host "🔗 ENDPOINTS DISPONIBLES:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Mock Server:        http://127.0.0.1:8501" -ForegroundColor Cyan
    Write-Host "  Backend API:        http://127.0.0.1:9000" -ForegroundColor Cyan
    Write-Host "  API Docs:           http://127.0.0.1:9000/docs" -ForegroundColor Cyan
    Write-Host "  Health Check:       http://127.0.0.1:9000/healthz" -ForegroundColor Cyan
    Write-Host "  Mock Stats:         http://127.0.0.1:8501/stats" -ForegroundColor Cyan
    Write-Host ""
}

function Cleanup {
    Write-Log ""
    Write-Log "Deteniendo servicios..." "Warning"
    
    foreach ($service in @("mock_server", "backend")) {
        if ($ProcessIds[$service]) {
            Write-Log "  Deteniendo $service (PID: $($ProcessIds[$service]))..." "Info"
            Stop-Process -Id $ProcessIds[$service] -Force -ErrorAction SilentlyContinue
        }
    }
    
    Write-Log "✓ Sistema detenido" "Success"
}

# Trap para limpieza al salir
trap {
    Cleanup
    exit 1
}

# Ejecución principal
Print-Banner

# Limpiar log anterior
if (Test-Path $ProcessLog) {
    Remove-Item $ProcessLog -Force
}

Write-Log "Iniciando desde: $ScriptRoot" "Debug"
Write-Log "PowerShell: $($PSVersionTable.PSVersion.Major).$($PSVersionTable.PSVersion.Minor)" "Debug"

try {
    # Iniciar servicios según modo
    switch ($Mode) {
        "all" {
            Start-MockServer
            Start-Backend
            Print-Status
            
            if (-not $NoWait) {
                Write-Host "✓ Sistema completamente funcional" -ForegroundColor Green
                Write-Host "Presiona Ctrl+C para detener`n" -ForegroundColor Green
                
                # Mantener proceso vivo
                while ($true) {
                    Start-Sleep -Seconds 1
                }
            }
        }
        "mock" {
            Start-MockServer
            Print-Status
        }
        "backend" {
            Start-Backend
            Print-Status
        }
        "ragas" {
            Write-Log "Asegurando que Mock Server está corriendo..." "Info"
            if (-not $ProcessIds["mock_server"]) {
                Start-MockServer
            }
            Run-RAGAS
        }
        default {
            Write-Log "Modo desconocido: $Mode" "Error"
            exit 1
        }
    }
}
finally {
    Cleanup
}
