#!/usr/bin/env python3
"""
Verifica disponibilidad publica del sistema (VPS + HTTPS + endpoints).
Uso:
  python scripts/verify_public_deployment.py https://tu-dominio.com
"""

import json
import socket
import ssl
import sys
from urllib import request
from urllib.parse import urlparse


def _https_get(url: str, timeout: int = 10) -> dict:
    try:
        req = request.Request(url, headers={"User-Agent": "ProyectoFinal-Validator/1.0"})
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(500).decode("utf-8", errors="ignore")
            return {"ok": True, "status": resp.status, "body_sample": body[:200]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _cert_info(hostname: str, port: int = 443) -> dict:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls:
            cert = tls.getpeercert()
            return {
                "subject": cert.get("subject"),
                "issuer": cert.get("issuer"),
                "notBefore": cert.get("notBefore"),
                "notAfter": cert.get("notAfter"),
                "tls_version": tls.version(),
            }


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/verify_public_deployment.py https://tu-dominio.com")
        return 2

    base_url = sys.argv[1].rstrip("/")
    parsed = urlparse(base_url)
    hostname = parsed.hostname

    if parsed.scheme != "https" or not hostname:
        print("La URL debe ser HTTPS valida, por ejemplo: https://clinico.midominio.com")
        return 2

    checks = {
        "frontend": _https_get(f"{base_url}/"),
        "backend_health": _https_get(f"{base_url}/api/v1/ragas/health"),
        "agent_health": _https_get(f"{base_url}/agent/healthz"),
    }

    cert = {}
    try:
        cert = _cert_info(hostname)
    except Exception as exc:
        cert = {"error": str(exc)}

    report = {
        "base_url": base_url,
        "checks": checks,
        "certificate": cert,
    }

    readiness = all(item.get("ok") for item in checks.values()) and "error" not in cert
    report["ready_public_delivery"] = readiness

    print(json.dumps(report, indent=2))

    out_path = "docs/public_deployment_verification.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReporte guardado en: {out_path}")

    return 0 if readiness else 1


if __name__ == "__main__":
    sys.exit(main())
