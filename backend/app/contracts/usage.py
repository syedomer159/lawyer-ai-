from pydantic import BaseModel


class RoleUsage(BaseModel):
    role: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float  # sum of known costs
    unpriced_calls: int  # calls whose cost the provider could not report


class UsageSummary(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    by_role: list[RoleUsage]
