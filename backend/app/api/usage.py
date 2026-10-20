from fastapi import APIRouter

from app.api.deps import StoreDep
from app.contracts.usage import UsageSummary

router = APIRouter(prefix="/api/cases/{case_id}", tags=["usage"])


@router.get("/usage")
def get_usage(store: StoreDep) -> UsageSummary:
    """Tokens and cost of every LLM call made for this case, by role and model."""
    return store.usage_summary()
