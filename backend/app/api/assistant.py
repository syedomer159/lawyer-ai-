from fastapi import APIRouter

from app.agents import assistant
from app.api.deps import CaseDep, EmbedderDep, SettingsDep, StoreDep
from app.contracts.assistant import ChatMessage, Question

router = APIRouter(prefix="/api/cases/{case_id}/assistant", tags=["assistant"])


@router.get("")
def list_messages(store: StoreDep) -> list[ChatMessage]:
    return assistant.list_messages(store)


@router.post("")
async def ask(
    body: Question, case: CaseDep, store: StoreDep, settings: SettingsDep, embedder: EmbedderDep
) -> list[ChatMessage]:
    """Ask about this case; returns the whole conversation with the new answer."""
    await assistant.ask(case, store, settings, embedder, body.text)
    return assistant.list_messages(store)
