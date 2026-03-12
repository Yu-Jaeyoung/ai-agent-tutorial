from typing import Literal

from pydantic import BaseModel


class HandoffData(BaseModel):
    issue_type: str | None = None
    issue_description: str | None = None
    reason: str | None = None


class MenuItem(BaseModel):
    name: str
    category: str
    price: float
    ingredients: list[str]
    allergens: list[str]
    spice_level: str
    dietary_notes: list[str]


class PendingFlowState(BaseModel):
    agent_name: str | None = None
    flow_kind: Literal["menu", "order", "reservation", "complaints"] | None = None
    stage: Literal["awaiting_details", "awaiting_confirmation", "completed"] | None = None


class RestaurantRunContext(BaseModel):
    active_agent_name: str | None = None
    latest_assistant_text: str = ""
    pending_flow_state: PendingFlowState | None = None


class InputGuardrailDecision(BaseModel):
    allow: bool
    category: Literal["allowed", "off_topic", "inappropriate_language"]
    fallback_message: str = ""
    reason: str = ""


class OutputGuardrailDecision(BaseModel):
    allow: bool
    violations: list[str] = []
    fallback_message: str = ""
