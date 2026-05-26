#!/usr/bin/env python3
"""
Genera un paquete de evidencia local para la entrega.
- Ejecuta readiness de rubrica
- Ejecuta benchmark de inferencia
- Ejecuta validacion general
- Resume rutas de artefactos en un JSON consolidado
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _run(script_rel_path: str) -> dict:
    script_path = ROOT / script_rel_path
    cmd = [str(ROOT / ".venv" / "bin" / "python.exe"), str(script_path)]
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "script": script_rel_path,
            "exit_code": result.returncode,
            "stdout_tail": "\n".join(result.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(result.stderr.splitlines()[-20:]),
        }
    except Exception as exc:
        return {
            "script": script_rel_path,
            "exit_code": -1,
            "error": str(exc),
        }


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    executions = [
        _run("scripts/rubric_readiness_check.py"),
        _run("scripts/benchmark_inference.py"),
        _run("scripts/validate_system.py"),
    ]

    artifacts = {
        "rubric_readiness_report": str((DOCS / "rubric_readiness_report.json").resolve()),
        "inference_latency_report": str((DOCS / "inference_latency_report.json").resolve()),
        "cloudflare_verification": str((DOCS / "cloudflare_verification.json").resolve()),
        "public_deployment_verification": str((DOCS / "public_deployment_verification.json").resolve()),
    }

    summary = {
        "generated_at": datetime.now().isoformat(),
        "executions": executions,
        "artifacts": artifacts,
    }

    out_file = DOCS / "evidence_bundle_summary.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nResumen guardado en: {out_file}")


if __name__ == "__main__":
    main()
