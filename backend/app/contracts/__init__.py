"""API contract: every request/response model lives here. The frontend types are generated
from the OpenAPI schema these produce (`npm run gen:api`), never hand-written."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model_profile: str
