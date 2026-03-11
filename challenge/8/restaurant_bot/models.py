from pydantic import BaseModel


# use on_handoff to run function if handoff happens.
# ex: show where handoff happens in UI
class HandoffData(BaseModel):
    issue_type: str | None = None
    issue_description: str | None = None
    reason: str | None = None
