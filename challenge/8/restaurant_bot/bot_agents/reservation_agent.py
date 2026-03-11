from agents import Agent

from ..guardrails import restaurant_output_guardrail
from ..instruction import reservation_agent_instruction

reservation_agent = Agent(
    name="Reservation Agent",
    instructions=reservation_agent_instruction,
    model="gpt-4o-mini",
    output_guardrails=[restaurant_output_guardrail],
)
