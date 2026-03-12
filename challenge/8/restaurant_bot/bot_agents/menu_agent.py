from agents import Agent

from ..guardrails import restaurant_output_guardrail
from ..instruction import menu_agent_instruction, menu_list
from ..menu_tools import get_menu_item_details, search_menu_items

menu_agent = Agent(
    name="Menu Agent",
    instructions=f"{menu_agent_instruction}\n\n{menu_list}",
    model="gpt-4o-mini",
    output_guardrails=[restaurant_output_guardrail],
    tools=[search_menu_items, get_menu_item_details],
)
