from agents import Agent

from ..guardrails import restaurant_input_guardrail, restaurant_output_guardrail
from ..instruction import order_agent_instruction
from ..menu_tools import get_menu_item_details, search_menu_items
from ..order_tools import calculate_order_total, simulate_payment

order_agent = Agent(
    name="Order Agent",
    instructions=order_agent_instruction,
    model="gpt-4o-mini",
    input_guardrails=[restaurant_input_guardrail],
    output_guardrails=[restaurant_output_guardrail],
    tools=[search_menu_items, get_menu_item_details, calculate_order_total, simulate_payment],
)
