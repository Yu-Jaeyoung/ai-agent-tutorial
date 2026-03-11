from agents import Agent

from ..instruction import menu_agent_instruction, menu_list

menu_agent = Agent(
    name="Menu Agent",
    instructions=f"{menu_agent_instruction}\n\n{menu_list}",
)
