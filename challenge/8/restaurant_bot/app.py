import asyncio
from typing import Any

import dotenv
import streamlit as st
from agents import Runner, SQLiteSession

from .bot_agents import triage_agent
from .handoffs import consume_handoff_events
from .instruction import menu_list

dotenv.load_dotenv()

HANDOFF_HISTORY_SESSION_KEY = "handoff_history"
TEXT_PLACEHOLDER_SESSION_KEY = "text_placeholder"


def get_session() -> SQLiteSession:
    if "session" not in st.session_state:
        st.session_state["session"] = SQLiteSession(
            "chat-history",
            "customer-support-memory.db",
        )
    return st.session_state["session"]


def get_handoff_history() -> list[list[dict[str, str]]]:
    return st.session_state.setdefault(HANDOFF_HISTORY_SESSION_KEY, [])


def clear_ui_state() -> None:
    st.session_state.pop(TEXT_PLACEHOLDER_SESSION_KEY, None)
    st.session_state[HANDOFF_HISTORY_SESSION_KEY] = []
    st.session_state["handoff_events"] = []


def format_handoff_event(event: dict[str, str]) -> str:
    title = f"[{event['from_agent_name']} -> {event['to_agent_name']}]"
    details = [
        event.get("reason", "").strip(),
        event.get("issue_type", "").strip(),
        event.get("issue_description", "").strip(),
    ]
    details = [detail for detail in details if detail]

    if not details:
        return title

    return f"{title} {' | '.join(details)}"


def render_handoff_trace(
    events: list[dict[str, str]],
    placeholder: Any | None = None,
) -> None:
    if placeholder is None:
        if not events:
            return

        st.markdown("**Handoff Trace**")
        for event in events:
            st.caption(format_handoff_event(event))
        return

    placeholder.empty()
    if not events:
        return

    with placeholder.container():
        st.markdown("**Handoff Trace**")
        for event in events:
            st.caption(format_handoff_event(event))


def extract_assistant_text(message: dict) -> str:
    content = message.get("content", [])
    texts: list[str] = []

    if not isinstance(content, list):
        return ""

    for item in content:
        if not isinstance(item, dict):
            continue

        if item.get("type") in {"text", "output_text"}:
            text = item.get("text", "")
            if text:
                texts.append(text)

    return "\n".join(texts)


async def paint_history(session: SQLiteSession):
    messages = await session.get_items()
    handoff_history = get_handoff_history()
    assistant_index = 0

    for message in messages:
        if "role" not in message:
            continue

        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
                continue

            if message.get("type") != "message":
                continue

            turn_handoffs = []
            if assistant_index < len(handoff_history):
                turn_handoffs = handoff_history[assistant_index]

            render_handoff_trace(turn_handoffs)

            assistant_text = extract_assistant_text(message)
            if assistant_text:
                st.write(assistant_text.replace("$", "\\$"))

            assistant_index += 1


async def run_agent(
    message: str,
    session: SQLiteSession,
):
    consume_handoff_events()

    with st.chat_message("assistant"):
        handoff_placeholder = st.empty()
        text_placeholder = st.empty()
        response = ""
        turn_handoffs: list[dict[str, str]] = []

        st.session_state[TEXT_PLACEHOLDER_SESSION_KEY] = text_placeholder

        try:
            stream = Runner.run_streamed(
                triage_agent,
                message,
                session=session,
            )

            async for event in stream.stream_events():
                new_handoffs = consume_handoff_events()
                if new_handoffs:
                    turn_handoffs.extend(new_handoffs)
                    render_handoff_trace(turn_handoffs, handoff_placeholder)

                if event.type != "raw_response_event":
                    continue

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response.replace("$", "\\$"))

            new_handoffs = consume_handoff_events()
            if new_handoffs:
                turn_handoffs.extend(new_handoffs)
                render_handoff_trace(turn_handoffs, handoff_placeholder)

            get_handoff_history().append(turn_handoffs)
        except Exception as exc:
            text_placeholder.error(f"에이전트 실행 중 오류가 발생했습니다: {exc}")


def render_sidebar(session: SQLiteSession) -> None:
    with st.sidebar:
        st.subheader("Debug")

        reset = st.button("Reset memory")
        if reset:
            asyncio.run(session.clear_session())
            clear_ui_state()
            st.rerun()

        st.caption("Entry Agent")
        st.code(triage_agent.name)

        with st.expander("Sample Menu Data", expanded=False):
            st.code(menu_list.strip())

        with st.expander("Session Items", expanded=False):
            st.write(asyncio.run(session.get_items()))


def main():
    st.set_page_config(
        page_title="Restaurant Bot",
        layout="centered",
    )
    st.title("Restaurant Bot")
    st.caption("Triage Agent를 시작점으로 Menu, Order, Reservation Agent를 handoff로 테스트합니다.")

    session = get_session()

    asyncio.run(paint_history(session))
    render_sidebar(session)

    message = st.chat_input("메뉴, 주문, 예약 관련 요청을 입력하세요.")

    if message:
        if TEXT_PLACEHOLDER_SESSION_KEY in st.session_state:
            st.session_state[TEXT_PLACEHOLDER_SESSION_KEY].empty()

        with st.chat_message("user"):
            st.write(message)

        asyncio.run(run_agent(message, session))
