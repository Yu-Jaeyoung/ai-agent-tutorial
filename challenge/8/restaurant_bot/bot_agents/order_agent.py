from agents import Agent

from ..instruction import order_agent_instruction

order_agent = Agent(
    name="Order Agent",
    instructions=order_agent_instruction,
)
