import re
from typing import Any

INJECTION_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUNION\b",
    r"\bSELECT\b",
    r"\bINSERT\b",
    r"\bEXEC\b",
    r"\bUPDATE\b",
    r"\bALTER\b",
    r"\b--\b",
    r"\b;\b",
]
PII_PATTERN = re.compile(r"(\b\d{3}-\d{2}-\d{4}\b|\b\d{16}\b|\b\d{15}\b|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)")


def sanitize_user_input(value: str) -> str:
    text = value.strip()
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in INJECTION_PATTERNS):
        raise ValueError("Solicitud bloqueada por posibles patrones de inyección.")
    return text


def mask_pii_in_response(value: Any) -> Any:
    if isinstance(value, str):
        return PII_PATTERN.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: mask_pii_in_response(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_pii_in_response(v) for v in value]
    return value
