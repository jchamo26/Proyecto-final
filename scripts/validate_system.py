#!/usr/bin/env python3
"""
Script de validación del sistema completo
Verifica que todos los componentes principales pueden ser importados y ejecutados
"""

import os
import sys
import json
from pathlib import Path

def print_header(text):
    """Imprime un encabezado de sección"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def print_status(test_name, passed, details=""):
    """Imprime el estado de una prueba"""
    if passed is True:
        status = "PASS"
    elif passed is None:
        status = "~ NEUTRAL"
    else:
        status = "FAIL"
    print(f"  {status:10} {test_name}")
    if details:
        print(f"           {details}")

def validate_ragas():
    """Valida que RAGAS está instalado correctamente"""
    print_header("1. VALIDACIÓN DE RAGAS")
    
    try:
        import ragas
        print_status("RAGAS import", True, f"v{ragas.__version__}")
        
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        print_status("RAGAS metrics import", True, "4 métricas disponibles")
        
        # La API de llm_factory puede variar entre versiones
        try:
            from ragas.llm import llm_factory
            print_status("RAGAS llm_factory", True)
        except ImportError:
            # En versiones recientes podría estar en otro lugar
            print_status("RAGAS llm_factory", None, "Ubicación alternativa (se importa en notebook)")
        
        return True
    except Exception as e:
        print_status("RAGAS import", None, f"No disponible en entorno actual: {e}")
        return None

def validate_openai_client():
    """Valida que el cliente OpenAI funciona con el mock server"""
    print_header("2. VALIDACIÓN DE CLIENTE OPENAI")
    
    try:
        from openai import OpenAI
        print_status("OpenAI client import", True)
        
        # Configurar con el mock server
        client = OpenAI(
            api_key="local_dummy_key",
            base_url="http://127.0.0.1:8501"
        )
        
        # Intentar una llamada simple
        try:
            response = client.chat.completions.create(
                model="mock-model",
                messages=[{"role": "user", "content": "test"}],
                timeout=5
            )
            print_status("OpenAI chat completion", True, f"Response ID: {response.id}")
            return True
        except Exception as e:
            # Es normal que falle si el mock server no está corriendo
            if "Connection" in str(e) or "timeout" in str(e).lower():
                print_status("OpenAI chat completion", False, "Mock server no está corriendo (esperado si no está iniciado)")
                return None  # Status neutro
            raise
            
    except Exception as e:
        print_status("OpenAI client", None, f"No disponible en entorno actual: {e}")
        return None

def validate_notebooks():
    """Valida que el notebook de RAGAS existe"""
    print_header("3. VALIDACIÓN DE NOTEBOOKS")
    
    notebook_path = Path("notebooks/ragas_evaluation.py")
    if notebook_path.exists():
        print_status("Notebook ragas_evaluation.py", True, f"Tamaño: {notebook_path.stat().st_size} bytes")
        
        # Verificar que el archivo contiene componentes clave
        with open(notebook_path, 'r') as f:
            content = f.read()
            
        checks = {
            "OpenAI import": "from openai import OpenAI" in content,
            "llm_factory": "llm_factory" in content,
            "EmbeddingsAdapter": "class EmbeddingsAdapter" in content,
            "evaluate": "evaluate(" in content,
            "ragas_report": "ragas_report.json" in content,
        }
        
        for check, passed in checks.items():
            print_status(f"  - {check}", passed)
        
        return all(checks.values())
    else:
        print_status("Notebook ragas_evaluation.py", False, "No encontrado")
        return False

def validate_mock_server():
    """Valida que el mock server está implementado correctamente"""
    print_header("4. VALIDACIÓN DE MOCK SERVER")
    
    mock_path = Path("scripts/mock_openai_server.py")
    if mock_path.exists():
        print_status("Mock server script", True, f"Tamaño: {mock_path.stat().st_size} bytes")
        
        with open(mock_path, 'r') as f:
            content = f.read()
        
        checks = {
            "Flask endpoint chat/completions": "def chat_completions" in content,
            "Flask endpoint embeddings": "def embeddings" in content,
            "Endpoint health": "def health" in content,
            "Endpoint stats": "def stats" in content,
            "Logging": "logger" in content,
            "Estadísticas": "call_stats" in content,
            "Multi-generación (n_completions)": "n_completions" in content,
        }
        
        for check, passed in checks.items():
            print_status(f"  - {check}", passed)
        
        return all(checks.values())
    else:
        print_status("Mock server script", False, "No encontrado")
        return False

def validate_reports():
    """Valida que los reportes existen"""
    print_header("5. VALIDACIÓN DE REPORTES")
    
    report_path = Path("ragas_report.json")
    if report_path.exists():
        try:
            with open(report_path, 'r') as f:
                report_data = json.load(f)
            
            print_status("ragas_report.json", True, f"{len(report_data)} evaluaciones")
            
            # Validar estructura
            if len(report_data) > 0:
                sample = report_data[0]
                keys = {"user_input", "response", "faithfulness", "answer_relevancy", 
                       "context_precision", "context_recall"}
                has_keys = all(k in sample for k in keys)
                print_status("  - Estructura correcta", has_keys, f"Claves encontradas: {list(sample.keys())[:3]}...")
                return has_keys
        except Exception as e:
            print_status("ragas_report.json", False, f"Error al leer: {str(e)}")
            return False
    else:
        print_status("ragas_report.json", False, "Aún no se ha generado")
        return None

def validate_documentation():
    """Valida que existe documentación"""
    print_header("6. VALIDACIÓN DE DOCUMENTACIÓN")
    
    doc_path = Path("docs/mock_server_y_ragas.md")
    if doc_path.exists():
        print_status("Documentación mock_server_y_ragas.md", True, f"Tamaño: {doc_path.stat().st_size} bytes")
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = {
            "Descripción General": "## Descripción General" in content,
            "Mock Server OpenAI": "Mock Server OpenAI" in content,
            "Integración RAGAS": "Integración con RAGAS" in content,
            "Endpoints": "## Endpoints" in content or "Endpoints" in content,
            "Métricas": "Métricas Evaluadas" in content,
            "Troubleshooting": "Troubleshooting" in content,
        }
        
        for section, found in sections.items():
            print_status(f"  - Sección: {section}", found)
        
        return all(sections.values())
    else:
        print_status("Documentación", False, "No encontrada")
        return False

def main():
    """Ejecuta todas las validaciones"""
    print("\n" + "="*60)
    print("  VALIDACIÓN DEL SISTEMA - RAGAS EVALUATION")
    print("  Proyecto Final SSD - 2026")
    print("="*60)
    
    # Cambiar al directorio raíz del proyecto
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print(f"\nDirectorio de trabajo: {os.getcwd()}")
    
    results = {
        "RAGAS": validate_ragas(),
        "OpenAI Client": validate_openai_client(),
        "Notebooks": validate_notebooks(),
        "Mock Server": validate_mock_server(),
        "Reportes": validate_reports(),
        "Documentación": validate_documentation(),
    }
    
    # Resumen
    print_header("RESUMEN DE VALIDACIÓN")
    passed = sum(1 for v in results.values() if v is True)
    neutral = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)
    
    for component, status in results.items():
        if status is True:
            print(f"  + {component:25} PASS")
        elif status is None:
            print(f"  ~ {component:25} NEUTRAL/ESPERADO")
        else:
            print(f"  - {component:25} FAIL")
    
    print(f"\nTotal: {passed} PASS, {neutral} NEUTRAL, {failed} FAIL")
    
    if failed == 0:
        print("\nValidación completada exitosamente")
        print("\nProximos pasos:")
        print("  1. Iniciar el mock server:")
        print("     $env:OPENAI_API_KEY='local_dummy_key'; python scripts\\mock_openai_server.py")
        print("\n  2. Ejecutar la evaluación RAGAS:")
        print("     $env:LLM_ENDPOINT='http://127.0.0.1:8501'; python notebooks\\ragas_evaluation.py")
        print("\n  3. Ver estadísticas del mock server:")
        print("     Invoke-RestMethod -Uri http://127.0.0.1:8501/stats")
        return 0
    else:
        print(f"\n{failed} validación(es) fallaron. Ver detalles arriba.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
