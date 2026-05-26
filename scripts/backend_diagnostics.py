#!/usr/bin/env python3
"""
Diagnóstico Completo del Backend
Identifica y reporta problemas de configuración, dependencias e inicialización
"""

import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import importlib
import asyncio

class BackendDiagnostics:
    """Herramienta de diagnóstico del backend"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "warnings": [],
            "errors": [],
            "summary": {"passed": 0, "failed": 0, "skipped": 0}
        }
        self.backend_path = Path(__file__).parent.parent / "backend"
    
    def log(self, message: str, level: str = "INFO"):
        """Registra mensaje"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level:8}] {message}")
    
    def check_python_version(self):
        """Verifica versión de Python"""
        self.log("Verificando Python...", "INFO")
        
        version = sys.version_info
        required = (3, 12)
        
        if version >= required:
            self.results["checks"]["python_version"] = {
                "status": "PASS",
                "version": f"{version.major}.{version.minor}.{version.micro}"
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["python_version"] = {
                "status": "FAIL",
                "version": f"{version.major}.{version.minor}.{version.micro}",
                "required": f"{required[0]}.{required[1]}+"
            }
            self.results["errors"].append(f"Python {required[0]}.{required[1]}+ requerido")
            self.results["summary"]["failed"] += 1
    
    def check_dependencies(self):
        """Verifica que las dependencias están instaladas"""
        self.log("Verificando dependencias...", "INFO")
        
        required_packages = [
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "pydantic",
            "openai",
            "ragas",
            "datasets",
            "httpx"
        ]
        
        missing = []
        
        for package in required_packages:
            try:
                importlib.import_module(package.replace("-", "_"))
            except ImportError:
                missing.append(package)
        
        if not missing:
            self.results["checks"]["dependencies"] = {
                "status": "PASS",
                "packages": len(required_packages)
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["dependencies"] = {
                "status": "FAIL",
                "missing": missing
            }
            self.results["errors"].append(f"Faltan paquetes: {', '.join(missing)}")
            self.results["summary"]["failed"] += 1
    
    def check_environment_variables(self):
        """Verifica variables de entorno requeridas"""
        self.log("Verificando variables de entorno...", "INFO")
        
        required_vars = [
            "SECRET_KEY",
            "FERNET_KEY",
            "OPENAI_API_KEY",
            "LLM_ENDPOINT"
        ]
        
        missing = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if not missing:
            self.results["checks"]["environment_variables"] = {
                "status": "PASS",
                "variables": len(required_vars)
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["environment_variables"] = {
                "status": "WARN",
                "missing": missing
            }
            self.results["warnings"].append(f"Variables faltantes: {', '.join(missing)}")
            self.results["summary"]["skipped"] += 1
    
    def check_backend_structure(self):
        """Verifica estructura de directorios del backend"""
        self.log("Verificando estructura del backend...", "INFO")
        
        required_files = [
            "app/__init__.py",
            "app/main.py",
            "app/api/__init__.py",
            "app/api/superuser.py",
            "app/api/ragas.py",
            "app/db/__init__.py",
            "app/db/models.py",
            "app/db/session.py",
            "app/services/__init__.py",
            "app/services/ragas_integration.py",
            "app/utils/optimization.py"
        ]
        
        missing_files = []
        
        for file_path in required_files:
            full_path = self.backend_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if not missing_files:
            self.results["checks"]["backend_structure"] = {
                "status": "PASS",
                "files": len(required_files)
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["backend_structure"] = {
                "status": "FAIL",
                "missing": missing_files
            }
            self.results["errors"].append(f"Archivos faltantes: {', '.join(missing_files)}")
            self.results["summary"]["failed"] += 1
    
    def check_imports(self):
        """Verifica que todos los imports funcionan"""
        self.log("Verificando imports del backend...", "INFO")
        
        # Agregar backend al path
        sys.path.insert(0, str(self.backend_path))
        
        import_checks = [
            ("app.main", "FastAPI app"),
            ("app.api.superuser", "SuperUser router"),
            ("app.api.ragas", "RAGAS router"),
            ("app.db.models", "Database models"),
            ("app.services.ragas_integration", "RAGAS service"),
            ("app.utils.optimization", "Optimization utils")
        ]
        
        failed_imports = []
        
        for module_name, description in import_checks:
            try:
                __import__(module_name)
                self.log(f"  ✓ {description}", "DEBUG")
            except ImportError as e:
                failed_imports.append((module_name, str(e)))
                self.log(f"  ✗ {description}: {str(e)}", "WARN")
        
        if not failed_imports:
            self.results["checks"]["imports"] = {
                "status": "PASS",
                "modules": len(import_checks)
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["imports"] = {
                "status": "FAIL",
                "failed": {name: str(err) for name, err in failed_imports}
            }
            self.results["errors"].append(f"Fallos de import en {len(failed_imports)} módulos")
            self.results["summary"]["failed"] += 1
    
    def check_fastapi_app(self):
        """Verifica que la aplicación FastAPI se puede crear"""
        self.log("Verificando aplicación FastAPI...", "INFO")
        
        sys.path.insert(0, str(self.backend_path))
        
        try:
            from app.main import app
            
            # Verificar que app tiene routers
            routes = [route.path for route in app.routes]
            
            self.results["checks"]["fastapi_app"] = {
                "status": "PASS",
                "routes": len(routes),
                "endpoints": routes[:5]  # Primeros 5
            }
            self.results["summary"]["passed"] += 1
            
            self.log(f"  ✓ App creada con {len(routes)} rutas", "DEBUG")
        
        except Exception as e:
            self.results["checks"]["fastapi_app"] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.results["errors"].append(f"Error creando FastAPI app: {str(e)}")
            self.results["summary"]["failed"] += 1
            self.log(f"  ✗ Error: {str(e)}", "ERROR")
    
    def check_mock_server(self):
        """Verifica conexión con mock server"""
        self.log("Verificando conexión con Mock Server...", "INFO")
        
        try:
            import httpx
            
            llm_endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8501")
            
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{llm_endpoint}/health")
                
                if response.status_code == 200:
                    self.results["checks"]["mock_server"] = {
                        "status": "PASS",
                        "endpoint": llm_endpoint
                    }
                    self.results["summary"]["passed"] += 1
                    self.log(f"  ✓ Mock server disponible", "DEBUG")
                else:
                    self.results["checks"]["mock_server"] = {
                        "status": "WARN",
                        "endpoint": llm_endpoint,
                        "status_code": response.status_code
                    }
                    self.results["warnings"].append("Mock server retorna status no-200")
                    self.results["summary"]["skipped"] += 1
        
        except Exception as e:
            self.results["checks"]["mock_server"] = {
                "status": "WARN",
                "error": str(e)
            }
            self.results["warnings"].append(f"No se puede conectar a mock server: {str(e)}")
            self.results["summary"]["skipped"] += 1
    
    def check_database(self):
        """Verifica configuración de base de datos"""
        self.log("Verificando configuración de base de datos...", "INFO")
        
        database_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
        
        if "sqlite" in database_url:
            # SQLite siempre funciona
            self.results["checks"]["database"] = {
                "status": "PASS",
                "type": "SQLite",
                "file": database_url.split("///")[-1]
            }
            self.results["summary"]["passed"] += 1
        elif "postgresql" in database_url:
            # Intentar conectar a PostgreSQL
            try:
                import psycopg2
                # Intentar conexión
                self.results["checks"]["database"] = {
                    "status": "WARN",
                    "type": "PostgreSQL",
                    "message": "Instalado pero no probado"
                }
                self.results["summary"]["skipped"] += 1
            except ImportError:
                self.results["checks"]["database"] = {
                    "status": "WARN",
                    "type": "PostgreSQL",
                    "message": "psycopg2 no instalado"
                }
                self.results["warnings"].append("psycopg2 no instalado para PostgreSQL")
                self.results["summary"]["skipped"] += 1
    
    def check_file_permissions(self):
        """Verifica permisos de archivos necesarios"""
        self.log("Verificando permisos de archivos...", "INFO")
        
        required_writable = [
            self.backend_path / "app",
            Path.cwd() / "startup.log",
            Path.cwd() / ".cache"
        ]
        
        issues = []
        
        for path_check in required_writable:
            if path_check.exists():
                try:
                    # Intentar crear archivo temporal
                    test_file = path_check / ".test_write"
                    if isinstance(path_check, Path) and path_check.is_dir():
                        test_file.touch()
                        test_file.unlink()
                except PermissionError:
                    issues.append(str(path_check))
        
        if not issues:
            self.results["checks"]["file_permissions"] = {
                "status": "PASS"
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["file_permissions"] = {
                "status": "WARN",
                "issues": issues
            }
            self.results["warnings"].append(f"Problemas de permisos: {', '.join(issues)}")
            self.results["summary"]["skipped"] += 1
    
    def run_syntax_checks(self):
        """Ejecuta verificación de sintaxis de archivos Python"""
        self.log("Verificando sintaxis de Python...", "INFO")
        
        python_files = list(self.backend_path.rglob("*.py"))
        syntax_errors = []
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), str(file_path), 'exec')
            except SyntaxError as e:
                syntax_errors.append({
                    "file": str(file_path.relative_to(self.backend_path)),
                    "error": str(e)
                })
        
        if not syntax_errors:
            self.results["checks"]["syntax"] = {
                "status": "PASS",
                "files_checked": len(python_files)
            }
            self.results["summary"]["passed"] += 1
        else:
            self.results["checks"]["syntax"] = {
                "status": "FAIL",
                "errors": syntax_errors
            }
            self.results["errors"].append(f"Errores de sintaxis en {len(syntax_errors)} archivos")
            self.results["summary"]["failed"] += 1
    
    def generate_report(self):
        """Genera reporte final"""
        print("\n" + "="*60)
        print("REPORTE DE DIAGNÓSTICO - BACKEND")
        print("="*60 + "\n")
        
        # Resumen
        print("📊 RESUMEN:")
        print(f"  ✓ PASSED: {self.results['summary']['passed']}")
        print(f"  ✗ FAILED: {self.results['summary']['failed']}")
        print(f"  ⚠ SKIPPED: {self.results['summary']['skipped']}")
        print()
        
        # Errores
        if self.results["errors"]:
            print("❌ ERRORES:")
            for error in self.results["errors"]:
                print(f"  - {error}")
            print()
        
        # Warnings
        if self.results["warnings"]:
            print("⚠ ADVERTENCIAS:")
            for warning in self.results["warnings"]:
                print(f"  - {warning}")
            print()
        
        # Checks detallados
        print("📋 CHECKS DETALLADOS:\n")
        for check_name, check_result in self.results["checks"].items():
            status = check_result.get("status", "UNKNOWN")
            symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⚠"
            print(f"{symbol} {check_name}: {status}")
        
        print("\n" + "="*60)
        
        # Recomendaciones
        if self.results["summary"]["failed"] > 0:
            print("\n🔧 ACCIONES RECOMENDADAS:")
            print("\n1. Instalar dependencias faltantes:")
            print("   pip install -r backend/requirements.txt")
            print("\n2. Configurar variables de entorno:")
            print("   export SECRET_KEY='your-secret-key'")
            print("   export OPENAI_API_KEY='local_dummy_key'")
            print("\n3. Iniciar mock server:")
            print("   python scripts/mock_openai_server.py")
            print("\n4. Ejecutar backend:")
            print("   cd backend && uvicorn app.main:app")
        
        # Guardar reporte
        report_file = Path("backend_diagnostic_report.json")
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Reporte guardado en: {report_file}")
        print("="*60 + "\n")
    
    def run_all_checks(self):
        """Ejecuta todos los checks"""
        print("\n🔍 INICIANDO DIAGNÓSTICO DEL BACKEND...\n")
        
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_environment_variables,
            self.check_backend_structure,
            self.check_imports,
            self.check_fastapi_app,
            self.check_mock_server,
            self.check_database,
            self.check_file_permissions,
            self.run_syntax_checks
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.log(f"Error en check: {str(e)}", "ERROR")
        
        self.generate_report()
        
        # Retornar código de salida
        return 0 if self.results["summary"]["failed"] == 0 else 1

def main():
    """Función principal"""
    diagnostics = BackendDiagnostics()
    exit_code = diagnostics.run_all_checks()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
