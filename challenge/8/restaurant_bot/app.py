import asyncio
from pathlib import Path
from typing import Any

import dotenv
import streamlit as st
from agents import Runner, SQLiteSession

from .bot_agents import triage_agent
from .handoffs import consume_handoff_events
from .instruction import menu_list

dotenv.load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_DB_PATH = BASE_DIR / "customer-support-memory.db"

HANDOFF_HISTORY_SESSION_KEY = "handoff_history"
CHAT_TURNS_SESSION_KEY = "chat_turns"
TEXT_PLACEHOLDER_SESSION_KEY = "text_placeholder"


def get_session() -> SQLiteSession:
    if "session" not in st.session_state:
        st.session_state["session"] = SQLiteSession(
            "chat-history",
            str(SESSION_DB_PATH),
        )
    return st.session_state["session"]


def get_handoff_history() -> list[list[dict[str, str]]]:
    return st.session_state.setdefault(HANDOFF_HISTORY_SESSION_KEY, [])


def get_chat_turns() -> list[dict[str, Any]]:
    return st.session_state.setdefault(CHAT_TURNS_SESSION_KEY, [])


def clear_ui_state() -> None:
    st.session_state.pop(TEXT_PLACEHOLDER_SESSION_KEY, None)
    st.session_state[HANDOFF_HISTORY_SESSION_KEY] = []
    st.session_state[CHAT_TURNS_SESSION_KEY] = []
    st.session_state["handoff_events"] = []


def format_handoff_event(event: dict[str, str]) -> str:
    return f"[{event['from_agent_name']} -> {event['to_agent_name']}]"


def render_handoff_trace(
    events: list[dict[str, str]],
    placeholder: Any | None = None,
) -> None:
    if placeholder is None:
        if not events:
            return

        for event in events:
            st.markdown(f"**{format_handoff_event(event)}**")
        return

    placeholder.empty()
    if not events:
        return

    with placeholder.container():
        for event in events:
            st.markdown(f"**{format_handoff_event(event)}**")


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


async def hydrate_chat_turns(session: SQLiteSession) -> None:
    if get_chat_turns():
        return

    messages = await session.get_items()
    handoff_history = get_handoff_history()
    assistant_index = 0
    current_user_message: str | None = None

    for message in messages:
        if "role" not in message:
            continue

        if message["role"] == "user":
            current_user_message = message["content"]
            continue

        if message.get("type") != "message":
            continue

        turn_handoffs = []
        if assistant_index < len(handoff_history):
            turn_handoffs = handoff_history[assistant_index]

        assistant_text = extract_assistant_text(message)
        if current_user_message is not None:
            get_chat_turns().append(
                {
                    "user": current_user_message,
                    "assistant": assistant_text,
                    "handoffs": turn_handoffs,
                }
            )
            current_user_message = None

        assistant_index += 1


def render_chat_turns() -> None:
    for turn in get_chat_turns():
        with st.chat_message("user"):
            st.write(turn["user"])

        with st.chat_message("assistant"):
            render_handoff_trace(turn["handoffs"])
            if turn["assistant"]:
                st.write(turn["assistant"].replace("$", "\\$"))


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
            get_chat_turns().append(
                {
                    "user": message,
                    "assistant": response,
                    "handoffs": turn_handoffs,
                }
            )
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

    asyncio.run(hydrate_chat_turns(session))
    render_chat_turns()
    render_sidebar(session)

    message = st.chat_input("메뉴, 주문, 예약 관련 요청을 입력하세요.")

    if message:
        if TEXT_PLACEHOLDER_SESSION_KEY in st.session_state:
            st.session_state[TEXT_PLACEHOLDER_SESSION_KEY].empty()

        with st.chat_message("user"):
            st.write(message)

        asyncio.run(run_agent(message, session))
