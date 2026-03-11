from agents import Agent

from ..guardrails import restaurant_output_guardrail
from ..instruction import complaints_agent_instruction

complaints_agent = Agent(
    name="Complaints Agent",
    instructions=complaints_agent_instruction,
    model="gpt-4o-mini",
    output_guardrails=[restaurant_output_guardrail],
)
