from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.ragas import router as ragas_router
from .api.superuser import router as superuser_router
from .core.config import settings
from .core.rate_limit import limiter
from .db.models import Base
from .db.session import engine
from .middleware.security import (
    AntiPromptInjectionMiddleware,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
    mask_pii_in_response,
)


def _allowed_origins() -> list[str]:
    candidates = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
    base_origin = settings.FRONTEND_HOST.rstrip("/")
    if base_origin and base_origin not in candidates:
        candidates.append(base_origin)

    for origin in ("http://localhost", "http://127.0.0.1", "https://localhost", "https://127.0.0.1"):
        if origin not in candidates:
            candidates.append(origin)

    return candidates


app = FastAPI(
    title="Sistema Clínico Inteligente",
    description="Backend FastAPI con interoperabilidad FHIR y API SuperUser.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.REQUIRE_HTTPS or settings.APP_ENV == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AntiPromptInjectionMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def response_filter(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await response.body()
            import json

            payload = json.loads(body.decode("utf-8"))
            masked = mask_pii_in_response(payload)
            return JSONResponse(status_code=response.status_code, content=masked)
        except Exception:
            pass
    return response


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(superuser_router, prefix="/api/v1")
app.include_router(ragas_router)


@app.get("/healthz")
async def health():
    return {"status": "ok"}
