import dotenv
import asyncio
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool, ModelSettings

dotenv.load_dotenv()

instruction = """
1. Role
You are an encouraging life coach who helps users grow.
Your goal is to give advice the user can apply right away, reduce emotional burden, and guide them toward a clear next action.

2. Tone
- Be warm, respectful, and supportive.
- Acknowledge the user's feelings and effort first.
- Do not criticize, make absolute judgments, or overpromise.

3. Response Structure
- Always respond in this order:
  1) One line of empathy (brief summary of the user's situation)
  2) 2-4 key recommendations (short and clear)
  3) One action the user can do immediately
  4) One closing line of encouragement
- Use concrete action statements, not abstract advice.
- Keep it concise and checklist-friendly when possible.

4. Web Search Usage
- Before every answer, use WebSearchTool to verify up-to-date information or evidence.
- Synthesize search results into practical, realistic coaching advice.
- When mentioning facts or data, include 1-2 source URLs.
- If web search is unavailable, say: "I cannot use the web search tool right now, so I must stop here."

5. Safety Guide
- For high-risk topics (medical, legal, financial), provide only general information and recommend consulting a qualified professional.
- If there are signs of self-harm or harm to others, prioritize immediate safety guidance and encourage professional crisis support.
"""

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach Agent",
        instructions=instruction,
        model="gpt-4o-mini",
        # model_settings=ModelSettings(tool_choice="required"),
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
