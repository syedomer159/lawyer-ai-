from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.analysis import CitationView


class Question(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    text: str
    # Checked in code: quotes not found in the cited chunk are flagged (verified=False); citations
    # to chunks that do not exist in this case are dropped, as there is no source to show.
    citations: list[CitationView]
