from agents import Agent

from ..guardrails import restaurant_output_guardrail
from ..instruction import order_agent_instruction

order_agent = Agent(
    name="Order Agent",
    instructions=order_agent_instruction,
    model="gpt-4o-mini",
    output_guardrails=[restaurant_output_guardrail],
)
