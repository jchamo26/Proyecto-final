#!/usr/bin/env python3
"""
Verifica configuracion basica de Cloudflare para la entrega final.
Requiere:
  - CLOUDFLARE_API_TOKEN
  - CLOUDFLARE_ZONE_ID
"""

import json
import os
import sys
from urllib import request
from urllib.error import HTTPError, URLError


API_BASE = "https://api.cloudflare.com/client/v4"


def _api_get(path: str, token: str) -> dict:
    req = request.Request(
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("success"):
        raise RuntimeError(f"Cloudflare API error: {payload.get('errors')}")
    return payload


def main() -> int:
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID", "").strip()

    if not token or not zone_id:
        print("Faltan variables: CLOUDFLARE_API_TOKEN y/o CLOUDFLARE_ZONE_ID")
        return 2

    try:
        dns = _api_get(f"/zones/{zone_id}/dns_records?per_page=200", token)
        ssl_mode = _api_get(f"/zones/{zone_id}/settings/ssl", token)
        waf = _api_get(f"/zones/{zone_id}/firewall/rules?per_page=200", token)
        rate_limits = _api_get(f"/zones/{zone_id}/rate_limits", token)
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"Error consultando Cloudflare: {exc}")
        return 1

    records = dns.get("result", [])
    proxied_count = sum(1 for item in records if item.get("proxied"))

    report = {
        "zone_id": zone_id,
        "dns_records_total": len(records),
        "dns_records_proxied": proxied_count,
        "ssl_mode": ssl_mode.get("result", {}).get("value"),
        "waf_rules_count": len(waf.get("result", [])),
        "rate_limits_count": len(rate_limits.get("result", [])),
        "checks": {
            "proxy_enabled": proxied_count > 0,
            "ssl_full_strict": ssl_mode.get("result", {}).get("value") == "strict",
            "waf_configured": len(waf.get("result", [])) > 0,
            "rate_limiting_configured": len(rate_limits.get("result", [])) > 0,
        },
    }

    print(json.dumps(report, indent=2))
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "cloudflare_verification.json")
    out_path = os.path.abspath(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReporte guardado en: {out_path}")

    return 0 if all(report["checks"].values()) else 3


if __name__ == "__main__":
    sys.exit(main())
