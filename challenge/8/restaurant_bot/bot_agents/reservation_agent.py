from agents import Agent

from ..instruction import reservation_agent_instruction

reservation_agent = Agent(
    name="Reservation Agent",
    instructions=reservation_agent_instruction,
)
