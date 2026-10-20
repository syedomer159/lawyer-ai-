from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.config import settings
from app.contracts import HealthResponse


def _operation_id(route: APIRoute) -> str:
    # Readable names in the generated TS client: `health`, not `health_api_health_get`.
    return route.name


app = FastAPI(title="Lawyer AI", generate_unique_id_function=_operation_id)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_profile=settings.model_profile)
