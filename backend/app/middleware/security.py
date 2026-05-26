import re
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
]

PII_PATTERNS = {
    "cedula": r"\b\d{6,10}\b(?=\s*(CC|c[ée]dula|documento))",
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "telefono": r"\b(3\d{9}|60\d{8})\b",
}

class AntiPromptInjectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            try:
                text = body.decode("utf-8")
            except Exception:
                text = ""
            # Binary payloads (for example ECG images in base64) can legitimately
            # contain tokens that would otherwise match prompt-injection regexes.
            # Skip strict scanning for those known upload routes.
            if "/inference/image" in request.url.path:
                return await call_next(request)
            for pattern in INJECTION_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
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
        return await call_next(request)


def sanitize_user_input(text: str) -> str:
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INPUT_REJECTED",
                    "message": "La consulta contiene patrones no permitidos.",
                    "code": "PROMPT_INJECTION_DETECTED",
                },
            )
    return text


def mask_pii_in_response(value):
    if isinstance(value, str):
        masked = re.sub(PII_PATTERNS["email"], lambda m: f"{m.group()[:3]}***@***.***", value)
        masked = re.sub(PII_PATTERNS["telefono"], lambda m: f"{m.group()[:3]}****{m.group()[-3:]}", masked)
        masked = re.sub(PII_PATTERNS["cedula"], lambda m: f"{m.group()[:2]}****{m.group()[-2:]}", masked)
        return masked
    if isinstance(value, dict):
        return {key: mask_pii_in_response(val) for key, val in value.items()}
    if isinstance(value, list):
        return [mask_pii_in_response(item) for item in value]
    return value
