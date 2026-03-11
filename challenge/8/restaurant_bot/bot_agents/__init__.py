from .menu_agent import menu_agent
from .order_agent import order_agent
from .reservation_agent import reservation_agent
from .triage_agent import triage_agent
from ..handoffs import build_agent_handoff

menu_agent.handoffs = [
    build_agent_handoff(
        from_agent_name=menu_agent.name,
        target_agent=triage_agent,
    ),
    build_agent_handoff(
        from_agent_name=menu_agent.name,
        target_agent=order_agent,
    ),
    build_agent_handoff(
        from_agent_name=menu_agent.name,
        target_agent=reservation_agent,
    ),
]

order_agent.handoffs = [
    build_agent_handoff(
        from_agent_name=order_agent.name,
        target_agent=triage_agent,
    ),
    build_agent_handoff(
        from_agent_name=order_agent.name,
        target_agent=menu_agent,
    ),
    build_agent_handoff(
        from_agent_name=order_agent.name,
        target_agent=reservation_agent,
    ),
]

reservation_agent.handoffs = [
    build_agent_handoff(
        from_agent_name=reservation_agent.name,
        target_agent=triage_agent,
    ),
    build_agent_handoff(
        from_agent_name=reservation_agent.name,
        target_agent=menu_agent,
    ),
    build_agent_handoff(
        from_agent_name=reservation_agent.name,
        target_agent=order_agent,
    ),
]

triage_agent.handoffs = [
    build_agent_handoff(
        from_agent_name=triage_agent.name,
        target_agent=menu_agent,
    ),
    build_agent_handoff(
        from_agent_name=triage_agent.name,
        target_agent=order_agent,
    ),
    build_agent_handoff(
        from_agent_name=triage_agent.name,
        target_agent=reservation_agent,
    ),
]

__all__ = [
    "menu_agent",
    "order_agent",
    "reservation_agent",
    "triage_agent",
]
