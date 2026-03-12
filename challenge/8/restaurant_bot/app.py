import asyncio
import os
from pathlib import Path
from typing import Any

import dotenv
import streamlit as st
from agents import Agent, Runner, SQLiteSession
from agents.exceptions import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from pydantic import BaseModel

from .bot_agents import AGENT_REGISTRY, triage_agent
from .handoffs import consume_handoff_events
from .instruction import menu_list

dotenv.load_dotenv()


def load_runtime_secrets() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return

    try:
        secret = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return

    if secret:
        os.environ["OPENAI_API_KEY"] = str(secret)


load_runtime_secrets()

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_DB_PATH = BASE_DIR / "restaurant-bot-memory.db"

HANDOFF_HISTORY_SESSION_KEY = "handoff_history"
CHAT_TURNS_SESSION_KEY = "chat_turns"
AGENT_RUNNING_SESSION_KEY = "agent_running"
PENDING_MESSAGES_SESSION_KEY = "pending_messages"
ACTIVE_AGENT_NAME_SESSION_KEY = "active_agent_name"


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


def get_pending_messages() -> list[str]:
    return st.session_state.setdefault(PENDING_MESSAGES_SESSION_KEY, [])


def get_active_agent() -> Agent[Any]:
    active_agent_name = st.session_state.setdefault(
        ACTIVE_AGENT_NAME_SESSION_KEY,
        triage_agent.name,
    )
    return AGENT_REGISTRY.get(active_agent_name, triage_agent)


def set_active_agent(agent: Agent[Any]) -> None:
    st.session_state[ACTIVE_AGENT_NAME_SESSION_KEY] = agent.name


def is_agent_running() -> bool:
    return st.session_state.setdefault(AGENT_RUNNING_SESSION_KEY, False)


def set_agent_running(is_running: bool) -> None:
    st.session_state[AGENT_RUNNING_SESSION_KEY] = is_running


def append_chat_turn(user_message: str) -> int:
    turns = get_chat_turns()
    turns.append(
        {
            "user": user_message,
            "assistant": "",
            "handoffs": [],
        }
    )
    return len(turns) - 1


def update_chat_turn(
    turn_index: int,
    *,
    assistant: str | None = None,
    handoffs: list[dict[str, str]] | None = None,
) -> None:
    turns = get_chat_turns()
    if not 0 <= turn_index < len(turns):
        return

    if assistant is not None:
        turns[turn_index]["assistant"] = assistant
    if handoffs is not None:
        turns[turn_index]["handoffs"] = list(handoffs)


def clear_ui_state() -> None:
    st.session_state[AGENT_RUNNING_SESSION_KEY] = False
    st.session_state[PENDING_MESSAGES_SESSION_KEY] = []
    st.session_state[ACTIVE_AGENT_NAME_SESSION_KEY] = triage_agent.name
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


def build_assistant_message_item(text: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "type": "message",
        "content": [
            {
                "type": "output_text",
                "text": text,
            }
        ],
    }


def extract_guardrail_fallback_message(
    exc: InputGuardrailTripwireTriggered | OutputGuardrailTripwireTriggered,
) -> str:
    output_info = exc.guardrail_result.output.output_info
    if isinstance(output_info, BaseModel):
        return getattr(output_info, "fallback_message", "") or "요청을 처리할 수 없어요."
    if isinstance(output_info, dict):
        return output_info.get("fallback_message") or "요청을 처리할 수 없어요."
    return "요청을 처리할 수 없어요."


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


def normalize_session_message_item(message: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(message)
    content = normalized.get("content")
    if not isinstance(content, list):
        return normalized

    normalized_content: list[Any] = []
    for item in content:
        if not isinstance(item, dict):
            normalized_content.append(item)
            continue

        normalized_item = dict(item)
        if normalized_item.get("type") == "text":
            normalized_item["type"] = "output_text"
        normalized_content.append(normalized_item)

    normalized["content"] = normalized_content
    return normalized


async def normalize_session_history(session: SQLiteSession) -> None:
    items = await session.get_items()
    normalized_items = [normalize_session_message_item(item) for item in items]

    if normalized_items == items:
        return

    await session.clear_session()
    await session.add_items(normalized_items)


def render_chat_turns() -> None:
    for turn in get_chat_turns():
        with st.chat_message("user"):
            st.write(turn["user"])

        with st.chat_message("assistant"):
            render_handoff_trace(turn["handoffs"])
            if turn["assistant"]:
                st.write(turn["assistant"].replace("$", "\\$"))


async def run_agent(
    starting_agent: Agent[Any],
    message: str,
    session: SQLiteSession,
    turn_index: int,
):
    consume_handoff_events()

    with st.chat_message("assistant"):
        handoff_placeholder = st.empty()
        text_placeholder = st.empty()
        response = ""
        turn_handoffs: list[dict[str, str]] = []

        try:
            stream = Runner.run_streamed(
                starting_agent,
                message,
                session=session,
            )

            async for event in stream.stream_events():
                new_handoffs = consume_handoff_events()
                if new_handoffs:
                    turn_handoffs.extend(new_handoffs)
                    update_chat_turn(turn_index, handoffs=turn_handoffs)
                    render_handoff_trace(turn_handoffs, handoff_placeholder)

                if event.type != "raw_response_event":
                    continue

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    update_chat_turn(turn_index, assistant=response)
                    text_placeholder.write(response.replace("$", "\\$"))

            new_handoffs = consume_handoff_events()
            if new_handoffs:
                turn_handoffs.extend(new_handoffs)
                update_chat_turn(turn_index, handoffs=turn_handoffs)
                render_handoff_trace(turn_handoffs, handoff_placeholder)

            get_handoff_history().append(turn_handoffs)
            update_chat_turn(
                turn_index,
                assistant=response,
                handoffs=turn_handoffs,
            )
            set_active_agent(stream.last_agent)
        except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered) as exc:
            fallback_message = extract_guardrail_fallback_message(exc)
            consume_handoff_events()
            handoff_placeholder.empty()
            text_placeholder.empty()
            text_placeholder.write(fallback_message)
            get_handoff_history().append([])
            update_chat_turn(
                turn_index,
                assistant=fallback_message,
                handoffs=[],
            )
            await session.add_items([build_assistant_message_item(fallback_message)])
            set_active_agent(starting_agent)
        except Exception as exc:
            error_message = f"에이전트 실행 중 오류가 발생했습니다: {exc}"
            text_placeholder.error(error_message)
            get_handoff_history().append(turn_handoffs)
            update_chat_turn(
                turn_index,
                assistant=error_message,
                handoffs=turn_handoffs,
            )
            set_active_agent(starting_agent)


def render_sidebar(session: SQLiteSession) -> None:
    with st.sidebar:
        st.subheader("Debug")

        reset = st.button("Reset memory", disabled=is_agent_running())
        if reset:
            asyncio.run(session.clear_session())
            clear_ui_state()
            st.rerun()

        st.caption("Current Agent")
        st.code(get_active_agent().name)

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
    st.caption(
        "메뉴 확인, 주문, 예약, 불편 사항 접수를 도와드려요."
    )

    session = get_session()

    asyncio.run(normalize_session_history(session))
    asyncio.run(hydrate_chat_turns(session))
    render_chat_turns()
    render_sidebar(session)

    message = st.chat_input(
        "메뉴, 주문, 예약, 불편 사항 관련 요청을 입력하세요.",
        disabled=is_agent_running(),
    )

    if message:
        get_pending_messages().append(message)
        set_agent_running(True)
        st.rerun()

    if not is_agent_running():
        if get_pending_messages():
            set_agent_running(True)
            st.rerun()
        return

    pending_messages = get_pending_messages()
    if not pending_messages:
        set_agent_running(False)
        return

    next_message = pending_messages.pop(0)
    turn_index = append_chat_turn(next_message)
    starting_agent = get_active_agent()

    with st.chat_message("user"):
        st.write(next_message)

    try:
        asyncio.run(run_agent(starting_agent, next_message, session, turn_index))
    finally:
        set_agent_running(bool(get_pending_messages()))

    st.rerun()
