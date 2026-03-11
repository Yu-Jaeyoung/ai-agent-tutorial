import asyncio

import dotenv
import streamlit as st
from agents import Runner, SQLiteSession, RunContextWrapper, function_tool

from .bot_agents import triage_agent
from .models import UserAccountContext

dotenv.load_dotenv()


@function_tool
def get_user_tier(wrapper: RunContextWrapper[UserAccountContext]):
    return f"The user {wrapper.context.customer_id} has a {wrapper.context.tier} account."


def get_user_account_context() -> UserAccountContext:
    return UserAccountContext(
        customer_id=1,
        name="nico",
        tier="basic",
    )


def get_session() -> SQLiteSession:
    if "session" not in st.session_state:
        st.session_state["session"] = SQLiteSession(
            "chat-history",
            "customer-support-memory.db",
        )
    return st.session_state["session"]


async def paint_history(session: SQLiteSession):
    messages = await session.get_items()
    for message in messages:
        if "role" not in message:
            continue

        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            elif message["type"] == "message":
                st.write(message["content"][0]["text"].replace("$", "\\$"))


async def run_agent(
    message: str,
    session: SQLiteSession,
    context: UserAccountContext,
):
    with st.chat_message("ai"):
        text_placeholder = st.empty()
        response = ""

        st.session_state["text_placeholder"] = text_placeholder

        stream = Runner.run_streamed(
            triage_agent,
            message,
            session=session,
            context=context,
        )

        async for event in stream.stream_events():
            if event.type != "raw_response_event":
                continue

            if event.data.type == "response.output_text.delta":
                response += event.data.delta
                text_placeholder.write(response.replace("$", "\\$"))


def main():
    session = get_session()
    user_account_ctx = get_user_account_context()

    asyncio.run(paint_history(session))

    message = st.chat_input("Write a message for your assistant")

    if message:
        if "text_placeholder" in st.session_state:
            st.session_state["text_placeholder"].empty()

        with st.chat_message("human"):
            st.write(message)

        asyncio.run(run_agent(message, session, user_account_ctx))

    with st.sidebar:
        reset = st.button("Reset memory")
        if reset:
            asyncio.run(session.clear_session())
        st.write(asyncio.run(session.get_items()))
