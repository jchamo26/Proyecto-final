from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.superuser import router as superuser_router
from app.api.ragas import router as ragas_router
from app.db.models import Base
from app.db.session import engine
from app.core.rate_limit import limiter
from app.middleware.security import AntiPromptInjectionMiddleware, mask_pii_in_response

app = FastAPI(
    title="Sistema Clínico Inteligente",
    description="Backend FastAPI con interoperabilidad FHIR y API SuperUser.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AntiPromptInjectionMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.middleware("http")
async def response_filter(request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            # Some responses are StreamingResponse and don't have .body()
            if hasattr(response, "body"):
                body = await response.body()
            else:
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
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
