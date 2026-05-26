#!/usr/bin/env python3
"""
Sistema de Startup Completo para Proyecto Final SSD
Inicia todos los servicios necesarios: Mock Server, Backend, Frontend
Maneja múltiples procesos y proporciona control centralizado
"""

import subprocess
import sys
import time
import os
import signal
import atexit
from pathlib import Path
from typing import Optional, Dict, List
import json
from datetime import datetime

class ServiceManager:
    """Gestor centralizado de servicios"""
    
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.services_config = self._load_config()
        self.log_file = Path("startup.log")
        self.start_time = datetime.now()
        
        # Registrar limpieza al salir
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Maneja señales de terminación"""
        print("\n\n⚠ Interrupción detectada. Deteniendo servicios...")
        self.cleanup()
        sys.exit(0)
    
    def _load_config(self) -> Dict:
        """Carga configuración de servicios"""
        return {
            "mock_server": {
                "name": "Mock OpenAI Server",
                "command": [sys.executable, "scripts/mock_openai_server.py"],
                "cwd": ".",
                "port": 8501,
                "env_vars": {
                    "OPENAI_API_KEY": "local_dummy_key",
                    "MOCK_LOG_LEVEL": "INFO"
                },
                "enabled": True,
                "wait_time": 2
            },
            "backend": {
                "name": "FastAPI Backend",
                "command": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9000", "--log-level", "info"],
                "cwd": "backend",
                "port": 9000,
                "env_vars": {
                    "SECRET_KEY": "testsecret123",
                    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
                    "SUPERUSER_EMAIL": "medico@example.com",
                    "SUPERUSER_PASSWORD": "SuperPass2026",
                    "SUPERUSER_LICENSE": "MED123456",
                    "FERNET_KEY": "R2pUXBafZ5-Xtqw3RlIscgDSwIT9WsoBUKIYr0MBtRc=",
                    "MLFLOW_TRACKING_URI": "http://localhost:5000",
                    "REDIS_URL": "redis://localhost:6379/0",
                    "LLM_ENDPOINT": "http://127.0.0.1:8501",
                    "ML_SERVICE_URL": "http://localhost:8100",
                    "DL_SERVICE_URL": "http://localhost:8200",
                    "FHIR_SERVER_URL": "http://localhost:8080/hapi-fhir-jpaserver",
                    "FRONTEND_HOST": "http://localhost",
                    "DATABASE_URL": "sqlite:///./test.db",
                    "MINIO_ROOT_USER": "minioadmin",
                    "MINIO_ROOT_PASSWORD": "minioadmin"
                },
                "enabled": True,
                "wait_time": 3
            },
            "ragas": {
                "name": "RAGAS Evaluation",
                "command": [sys.executable, "notebooks/ragas_evaluation.py"],
                "cwd": ".",
                "port": None,
                "env_vars": {
                    "LLM_ENDPOINT": "http://127.0.0.1:8501",
                    "OPENAI_API_KEY": "local_dummy_key"
                },
                "enabled": False,  # Se ejecuta bajo demanda
                "wait_time": 0
            }
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Registra mensaje en log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level:8}] {message}"
        print(log_msg)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    
    def start_service(self, service_name: str) -> bool:
        """Inicia un servicio"""
        if service_name not in self.services_config:
            self.log(f"Servicio desconocido: {service_name}", "ERROR")
            return False
        
        config = self.services_config[service_name]
        if not config.get("enabled"):
            self.log(f"Servicio {config['name']} está deshabilitado", "WARN")
            return False
        
        if service_name in self.processes:
            self.log(f"{config['name']} ya está corriendo", "WARN")
            return False
        
        try:
            # Preparar variables de entorno
            env = os.environ.copy()
            env.update(config.get("env_vars", {}))
            
            # Crear proceso
            cwd = Path(config["cwd"])
            if not cwd.exists():
                self.log(f"Directorio no existe: {cwd}", "ERROR")
                return False
            
            self.log(f"Iniciando {config['name']}...", "INFO")
            process = subprocess.Popen(
                config["command"],
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.processes[service_name] = process
            self.log(f"✓ {config['name']} iniciado (PID: {process.pid})", "INFO")
            
            if config.get("wait_time"):
                self.log(f"  Esperando {config['wait_time']}s para que se inicie...", "DEBUG")
                time.sleep(config["wait_time"])
            
            return True
            
        except Exception as e:
            self.log(f"✗ Error al iniciar {config['name']}: {str(e)}", "ERROR")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Detiene un servicio"""
        if service_name not in self.processes:
            return False
        
        process = self.processes[service_name]
        config = self.services_config[service_name]
        
        try:
            self.log(f"Deteniendo {config['name']}...", "INFO")
            process.terminate()
            
            try:
                process.wait(timeout=5)
                self.log(f"✓ {config['name']} detenido gracefully", "INFO")
            except subprocess.TimeoutExpired:
                self.log(f"  Forzando terminación de {config['name']}...", "WARN")
                process.kill()
                process.wait()
                self.log(f"✓ {config['name']} forzadamente detenido", "INFO")
            
            del self.processes[service_name]
            return True
            
        except Exception as e:
            self.log(f"Error al detener {config['name']}: {str(e)}", "ERROR")
            return False
    
    def start_all(self):
        """Inicia todos los servicios"""
        self.log("="*60, "INFO")
        self.log("INICIANDO SISTEMA COMPLETO", "INFO")
        self.log("="*60, "INFO")
        
        services_to_start = ["mock_server", "backend"]
        
        for service_name in services_to_start:
            if not self.start_service(service_name):
                self.log(f"Abortando inicio debido a fallo en {service_name}", "ERROR")
                self.cleanup()
                return False
        
        self.log("\n" + "="*60, "INFO")
        self.log("✓ TODOS LOS SERVICIOS INICIADOS EXITOSAMENTE", "INFO")
        self.log("="*60, "INFO")
        self._print_status()
        
        return True
    
    def _print_status(self):
        """Imprime estado de servicios"""
        print("\n📊 ESTADO DE SERVICIOS:\n")
        for service_name, config in self.services_config.items():
            if config.get("enabled"):
                is_running = service_name in self.processes
                status = "🟢 EJECUTANDO" if is_running else "🔴 DETENIDO"
                port_info = f" (Puerto: {config['port']})" if config['port'] else ""
                print(f"  {status}  {config['name']}{port_info}")
        
        print("\n📝 ENDPOINTS DISPONIBLES:\n")
        endpoints = {
            "Mock Server": "http://127.0.0.1:8501",
            "Backend API": "http://127.0.0.1:9000",
            "Backend Docs": "http://127.0.0.1:9000/docs",
            "Health Check": "http://127.0.0.1:9000/healthz"
        }
        for name, url in endpoints.items():
            print(f"  {name:20} {url}")
        
        print("\n💡 COMANDOS ÚTILES:\n")
        print("  - Ver logs:           tail -f startup.log")
        print("  - Detener servicios:  Presionar Ctrl+C")
        print("  - Ver estadísticas:   curl http://127.0.0.1:8501/stats")
        print("\n")
    
    def cleanup(self):
        """Limpia y detiene todos los servicios"""
        if not self.processes:
            return
        
        self.log("\nDeteniendo todos los servicios...", "INFO")
        
        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.log(f"Tiempo de ejecución: {elapsed:.1f}s", "INFO")
        self.log("Sistema completamente detenido", "INFO")
    
    def show_logs(self, service_name: str, lines: int = 20):
        """Muestra logs de un servicio"""
        if service_name not in self.processes:
            print(f"Servicio {service_name} no está en ejecución")
            return
        
        print(f"\n=== Últimas {lines} líneas de {service_name} ===\n")
        # Los logs van directamente a stdout
    
    def interactive_mode(self):
        """Modo interactivo"""
        while True:
            print("\n🎮 MENÚ DE CONTROL:")
            print("  1. Ver estado de servicios")
            print("  2. Iniciar servicio individual")
            print("  3. Detener servicio individual")
            print("  4. Ejecutar evaluación RAGAS")
            print("  5. Ver logs completos")
            print("  6. Salir")
            
            choice = input("\nSeleccionar opción (1-6): ").strip()
            
            if choice == "1":
                self._print_status()
            elif choice == "2":
                service = input("Servicio (mock_server/backend): ").strip()
                self.start_service(service)
            elif choice == "3":
                service = input("Servicio (mock_server/backend): ").strip()
                self.stop_service(service)
            elif choice == "4":
                print("Ejecutando RAGAS evaluation...")
                self.start_service("ragas")
            elif choice == "5":
                if self.log_file.exists():
                    print(open(self.log_file).read())
            elif choice == "6":
                break
            else:
                print("Opción inválida")

def main():
    """Función principal"""
    manager = ServiceManager()
    
    # Banner
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  SISTEMA DE STARTUP - PROYECTO FINAL SSD".center(58) + "║")
    print("║" + "  Sistema Clínico Inteligente 2026".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    # Limpiar log anterior
    if manager.log_file.exists():
        manager.log_file.unlink()
    
    manager.log(f"Iniciando desde: {os.getcwd()}", "INFO")
    manager.log(f"Python: {sys.version.split()[0]}", "INFO")
    
    # Iniciar servicios
    if manager.start_all():
        try:
            print("\n✓ Sistema completamente funcional")
            print("Presiona Ctrl+C para detener\n")
            
            # Mantener proceso vivo
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n")
    else:
        print("\n✗ No se pudo iniciar el sistema")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
