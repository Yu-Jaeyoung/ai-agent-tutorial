from agents import Agent

from ..instruction import triage_agent_instruction

triage_agent = Agent(
    name="Triage Agent",
    instructions=triage_agent_instruction,
)
