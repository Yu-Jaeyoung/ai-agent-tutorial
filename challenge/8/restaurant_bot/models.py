from typing import Literal

from pydantic import BaseModel


class HandoffData(BaseModel):
    issue_type: str | None = None
    issue_description: str | None = None
    reason: str | None = None


class InputGuardrailDecision(BaseModel):
    allow: bool
    category: Literal["allowed", "off_topic", "inappropriate_language"]
    fallback_message: str = ""
    reason: str = ""


class OutputGuardrailDecision(BaseModel):
    allow: bool
    violations: list[str] = []
    fallback_message: str = ""
