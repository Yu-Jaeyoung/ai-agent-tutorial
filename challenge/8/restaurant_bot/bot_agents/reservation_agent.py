from agents import Agent

from ..guardrails import restaurant_input_guardrail, restaurant_output_guardrail
from ..instruction import reservation_agent_instruction

reservation_agent = Agent(
    name="Reservation Agent",
    instructions=reservation_agent_instruction,
    model="gpt-4o-mini",
    input_guardrails=[restaurant_input_guardrail],
    output_guardrails=[restaurant_output_guardrail],
)
