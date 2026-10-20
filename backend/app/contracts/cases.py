from typing import Literal, get_args

from pydantic import BaseModel, Field

UserSide = Literal["defence", "prosecution"]
USER_SIDES: tuple[str, ...] = get_args(UserSide)


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    client: str = Field(min_length=1, max_length=200)
    user_side: UserSide = "defence"
    charges: list[str] = Field(default_factory=list)
    local_only: bool = False


class Case(BaseModel):
    # Not a subclass of CaseCreate: request defaults would make these optional in the response.
    id: str
    title: str
    client: str
    user_side: UserSide
    charges: list[str]
    local_only: bool
    embed_model: str
    created_at: str
