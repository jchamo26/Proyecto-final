import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions?",
    r"system\s*:",
    r"you are now",
    r"jailbreak",
    r"forget (your|all) (instructions?|rules?|constraints?)",
    r"act as (if you are|a)?",
    r"pretend (you are|to be)",
    r"override (safety|instructions?)",
    r"base64",
    r"###\s*(INSTRUCTION|SYSTEM|PROMPT)",
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
MAX_INPUT_LENGTH = 4000


def build_security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'"
        ),
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in build_security_headers().items():
            response.headers.setdefault(key, value)
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_url = str(request.url)
        if request_url.startswith("http://"):
            target = request_url.replace("http://", "https://", 1)
            return JSONResponse(status_code=307, headers={"Location": target})
        return await call_next(request)


def sanitize_user_input(value: str) -> str:
    text = (value or "").strip()
    if not text or len(text) > MAX_INPUT_LENGTH:
        raise ValueError("Solicitud vacía o demasiado larga.")
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in INJECTION_PATTERNS):
        raise ValueError("Solicitud bloqueada por posibles patrones de inyección.")
    return text


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_user_input(value)
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_payload(val) for key, val in value.items()}
    return value


def mask_pii_in_response(value: Any) -> Any:
    if isinstance(value, str):
        return PII_PATTERN.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: mask_pii_in_response(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_pii_in_response(v) for v in value]
    return value
