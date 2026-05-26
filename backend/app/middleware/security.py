import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import settings

MAX_INPUT_LENGTH = 4000
INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions?",
    r"system\s*:",
    r"you are now",
    r"\bDAN\b",
    r"jailbreak",
    r"forget (your|all) (instructions?|rules?|constraints?)",
    r"act as (if you are|a)?",
    r"pretend (you are|to be)",
    r"override (safety|instructions?)",
    r"base64",
    r"###\s*(INSTRUCTION|SYSTEM|PROMPT)",
    r"reveal (the )?(system|hidden) (prompt|instructions?)",
    r"developer\s*:",
    r"tool\s*:",
    r"\bDROP\b",
    r"\bUNION\b",
    r"\bSELECT\b",
    r"\bINSERT\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bALTER\b",
]

PII_PATTERNS = {
    "cedula": r"\b\d{6,10}\b(?=\s*(CC|c[ée]dula|documento))",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "telefono": r"\b(?:\+?57[-.\s]?)?(?:3\d{9}|60\d{8})\b",
    "numeric_id": r"\b\d{8,10}\b",
}


def _blocked_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": {
                "error": "INPUT_REJECTED",
                "message": "La consulta contiene patrones no permitidos.",
                "code": "PROMPT_INJECTION_DETECTED",
            }
        },
    )


def _contains_prompt_injection(text: str) -> bool:
    normalized = text.casefold()
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in INJECTION_PATTERNS)


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
        if not (settings.REQUIRE_HTTPS or settings.APP_ENV == "production"):
            return await call_next(request)

        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        request_url = str(request.url)

        if forwarded_proto == "http" or (not forwarded_proto and request_url.startswith("http://")):
            target = request_url.replace("http://", "https://", 1)
            return JSONResponse(
                status_code=307,
                content={"detail": "HTTPS requerido para esta ruta."},
                headers={"Location": target},
            )

        return await call_next(request)


class AntiPromptInjectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            request._body = body
            try:
                text = body.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            query_text = " ".join(request.query_params.values())
            combined = f"{query_text}\n{text}"
            if _contains_prompt_injection(combined):
                return _blocked_response()

        return await call_next(request)


def sanitize_user_input(text: str) -> str:
    if not isinstance(text, str):
        raise _blocked_response()

    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_INPUT_LENGTH:
        raise _blocked_response()

    if _contains_prompt_injection(cleaned):
        raise _blocked_response()

    return cleaned


def mask_pii_in_response(value):
    if isinstance(value, str):
        masked = re.sub(PII_PATTERNS["email"], lambda m: f"{m.group()[:3]}***@***.***", value)
        masked = re.sub(PII_PATTERNS["telefono"], lambda m: f"{m.group()[:3]}****{m.group()[-3:]}", masked)
        masked = re.sub(PII_PATTERNS["cedula"], lambda m: f"{m.group()[:2]}****{m.group()[-2:]}", masked)
        masked = re.sub(PII_PATTERNS["numeric_id"], lambda m: f"{m.group()[:2]}****{m.group()[-2:]}", masked)
        return masked

    if isinstance(value, dict):
        return {key: mask_pii_in_response(val) for key, val in value.items()}

    if isinstance(value, list):
        return [mask_pii_in_response(item) for item in value]

    return value
