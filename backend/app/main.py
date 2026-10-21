from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api import analysis, cases, documents, usage
from app.config import settings
from app.contracts import HealthResponse
from app.observability import setup_tracing


def _operation_id(route: APIRoute) -> str:
    # Readable names in the generated TS client: `health`, not `health_api_health_get`.
    return route.name


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    provider = setup_tracing(settings)
    yield
    if provider:
        provider.shutdown()  # flush pending spans


app = FastAPI(title="Lawyer AI", generate_unique_id_function=_operation_id, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(usage.router)
app.include_router(analysis.router)


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_profile=settings.model_profile)
