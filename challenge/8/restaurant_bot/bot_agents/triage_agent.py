from agents import Agent

from ..guardrails import restaurant_input_guardrail, restaurant_output_guardrail
from ..instruction import triage_agent_instruction

triage_agent = Agent(
    name="Triage Agent",
    instructions=triage_agent_instruction,
    model="gpt-4o-mini",
    input_guardrails=[restaurant_input_guardrail],
    output_guardrails=[restaurant_output_guardrail],
)
