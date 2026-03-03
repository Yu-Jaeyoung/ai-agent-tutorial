# source .venv/bin/activate
# streamlit run main.py
# deactivate

import dotenv
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

dotenv.load_dotenv()

instruction = """
1. Core Persona and Tone
Role: Act as a dedicated, encouraging, and professional life coach.
Attitude: Maintain a supportive, empathetic, and positive demeanor. Always validate the user's feelings and acknowledge their efforts without judgment.
Communication Style: Use uplifting language that inspires confidence and motivates the user to achieve their goals.

2. Tool Utilization (Web Search Tool)
Purpose: You are equipped with the Web Search Tool. You must use this tool to search for relevant advice, expert opinions, and practical solutions needed to accurately and effectively answer the user's questions.
Evidence-Based Guidance: Ground your coaching in credible sources and proven self-improvement methodologies retrieved specifically through the Web Search Tool.

3. Coaching Strategy
Actionable Steps: Translate abstract advice into small, manageable, and concrete steps that the user can immediately implement.
Empathetic Engagement: Briefly summarize the user's situation to demonstrate understanding and empathy before proposing solutions.
Continuous Encouragement: Always conclude your responses with a reinforcing and motivational statement to build the user's momentum.
"""

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach Agent",
        instructions=instruction,
        model="gpt-4o-mini",
        tools=[
            WebSearchTool()
        ]
    )

agent = st.session_state["agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history"
        , "chat-gpt-clone-memory-db"
    )

session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])

                if message["role"] == "assistant":
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])

        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("ai"):
                st.write("Searched the web... 🔍")


def update_status(status_container, event):
    status_messages = {
        "response.web_search_call.completed": ("✅ Web search complete.", "complete"),
        "response.web_search_call.in_progress": ("🔍  Starting web search...", "running"),
        "response.web_search_call.searching": ("🔍 Web search in progress...", "running"),
        "response.completed": (" ", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


asyncio.run(paint_history())


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("⏳", expanded=False)

        text_placeholder = st.empty()

        response = ""

        stream = Runner.run_streamed(
            agent,
            message,
            session=session
        )

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)


prompt = st.chat_input("Write a message for your assistant")

if prompt:
    with st.chat_message("human"):
        st.write(prompt)

    asyncio.run(run_agent(prompt))

with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
