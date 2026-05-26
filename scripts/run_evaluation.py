#!/usr/bin/env python3
"""
Script de inicialización rápida del sistema RAGAS Evaluation
Ejecuta el mock server y la evaluación de forma simplificada
"""

import subprocess
import sys
import time
import os
import signal
import platform

def start_mock_server():
    """Inicia el mock server en proceso separado"""
    print("\n" + "="*60)
    print("  INICIANDO MOCK SERVER OPENAI")
    print("="*60)
    
    env = os.environ.copy()
    env['OPENAI_API_KEY'] = 'local_dummy_key'
    
    print("Disponible en: http://127.0.0.1:8501")
    print("\nPresiona Ctrl+C para detener tanto el servidor como la evaluación\n")
    
    # Iniciar mock server
    cmd = [sys.executable, "scripts/mock_openai_server.py"]
    
    process = subprocess.Popen(
        cmd,
        env=env,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Esperar a que el servidor inicie
    time.sleep(2)
    
    return process

def run_evaluation():
    """Ejecuta la evaluación RAGAS"""
    print("\n" + "="*60)
    print("  EJECUTANDO EVALUACIÓN RAGAS")
    print("="*60 + "\n")
    
    env = os.environ.copy()
    env['LLM_ENDPOINT'] = 'http://127.0.0.1:8501'
    env['OPENAI_API_KEY'] = 'local_dummy_key'
    
    cmd = [sys.executable, "notebooks/ragas_evaluation.py"]
    
    result = subprocess.run(
        cmd,
        env=env,
        text=True
    )
    
    return result.returncode

def cleanup(mock_process):
    """Limpia recursos"""
    if mock_process:
        print("\n\nDeteniendo mock server...")
        mock_process.terminate()
        try:
            mock_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mock_process.kill()
        print("Mock server detenido")

def main():
    """Función principal"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  RAGAS EVALUATION SYSTEM".center(58) + "║")
    print("║" + "  Proyecto Final SSD - 2026".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    mock_process = None
    
    try:
        # Validar primero
        print("\n1. Validando sistema...")
        result = subprocess.run(
            [sys.executable, "scripts/validate_system.py"],
            capture_output=True,
            text=True
        )
        
        if "Total:" in result.stdout:
            # Extraer resumen de validación
            for line in result.stdout.split('\n'):
                if 'Total:' in line or 'Próximos pasos:' in line:
                    print(line)
        
        # Iniciar mock server
        print("\n2. Iniciando mock server...")
        mock_process = start_mock_server()
        
        # Ejecutar evaluación
        print("3. Ejecutando evaluación...")
        exit_code = run_evaluation()
        
        # Mostrar resultados
        print("\n" + "="*60)
        print("  EVALUACIÓN COMPLETADA")
        print("="*60)
        
        if exit_code == 0:
            print("\n✓ Evaluación ejecutada exitosamente")
            print("\nArchivos generados:")
            print("  - ragas_report.json (Resultados detallados)")
            print("\nVerificar estadísticas del mock server:")
            print("  Invoke-RestMethod -Uri 'http://127.0.0.1:8501/stats'")
        else:
            print(f"\n✗ La evaluación falló con código de salida: {exit_code}")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupción del usuario")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        return 1
    finally:
        cleanup(mock_process)

if __name__ == "__main__":
    sys.exit(main())
