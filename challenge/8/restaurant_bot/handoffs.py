from typing import Any

import streamlit as st
from agents import Agent, RunContextWrapper, handoff

from .models import HandoffData

HANDOFF_EVENTS_SESSION_KEY = "handoff_events"


def _append_handoff_event(
    *,
    from_agent_name: str,
    to_agent_name: str,
    input_data: HandoffData,
) -> None:
    events = st.session_state.setdefault(HANDOFF_EVENTS_SESSION_KEY, [])
    events.append(
        {
            "from_agent_name": from_agent_name,
            "to_agent_name": to_agent_name,
            "issue_type": input_data.issue_type or "",
            "issue_description": input_data.issue_description or "",
            "reason": input_data.reason or "",
        }
    )


def build_handoff_handler(from_agent_name: str, to_agent_name: str):
    def handle_handoff(
        _: RunContextWrapper[Any],
        input_data: HandoffData,
    ) -> None:
        _append_handoff_event(
            from_agent_name=from_agent_name,
            to_agent_name=to_agent_name,
            input_data=input_data,
        )

    return handle_handoff


def build_agent_handoff(
    *,
    from_agent_name: str,
    target_agent: Agent[Any],
):
    return handoff(
        agent=target_agent,
        on_handoff=build_handoff_handler(from_agent_name, target_agent.name),
        input_type=HandoffData,
    )


def consume_handoff_events() -> list[dict[str, str]]:
    events = list(st.session_state.get(HANDOFF_EVENTS_SESSION_KEY, []))
    st.session_state[HANDOFF_EVENTS_SESSION_KEY] = []
    return events
