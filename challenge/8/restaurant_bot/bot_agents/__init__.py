from .complaints_agent import complaints_agent
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
    build_agent_handoff(
        from_agent_name=menu_agent.name,
        target_agent=complaints_agent,
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
    build_agent_handoff(
        from_agent_name=order_agent.name,
        target_agent=complaints_agent,
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
    build_agent_handoff(
        from_agent_name=reservation_agent.name,
        target_agent=complaints_agent,
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
    build_agent_handoff(
        from_agent_name=triage_agent.name,
        target_agent=complaints_agent,
    ),
]

complaints_agent.handoffs = [
    build_agent_handoff(
        from_agent_name=complaints_agent.name,
        target_agent=triage_agent,
    ),
    build_agent_handoff(
        from_agent_name=complaints_agent.name,
        target_agent=menu_agent,
    ),
    build_agent_handoff(
        from_agent_name=complaints_agent.name,
        target_agent=order_agent,
    ),
    build_agent_handoff(
        from_agent_name=complaints_agent.name,
        target_agent=reservation_agent,
    ),
]

AGENT_REGISTRY = {
    triage_agent.name: triage_agent,
    menu_agent.name: menu_agent,
    order_agent.name: order_agent,
    reservation_agent.name: reservation_agent,
    complaints_agent.name: complaints_agent,
}

__all__ = [
    "AGENT_REGISTRY",
    "complaints_agent",
    "menu_agent",
    "order_agent",
    "reservation_agent",
    "triage_agent",
]
