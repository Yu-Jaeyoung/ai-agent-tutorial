import dotenv
import asyncio
import os
import streamlit as st
from openai import OpenAI
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool, ModelSettings

dotenv.load_dotenv()

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

client = OpenAI()

instruction = """
1. Role
You are a kind and encouraging Life Coach who helps users grow.
Your goal is to give practical advice the user can apply right away, reduce emotional burden, and guide them toward a clear next action.

2. Tone
- Be warm, respectful, and supportive.
- Acknowledge the user's feelings and effort first.
- Do not criticize, make absolute judgments, or overpromise.
- Always answer kindly.

3. Tool Definitions
- WebSearchTool(): Use this tool to find up-to-date external information, trends, statistics, and evidence from the web.
- FileSearchTool(): Use this tool to search the user's uploaded files and identify the user's goals, current situation, constraints, and preferences.

4. Required Tool Workflow (For Every User Question)
- Step 1: Use FileSearchTool() first to confirm what the user is aiming for (goal) and relevant personal context from uploaded files.
- Step 2: Use WebSearchTool() to collect current and reliable supporting information related to that goal.
- Step 3: Combine both results: personalize advice with FileSearchTool findings and support it with WebSearchTool evidence.
- Do not provide a final answer unless both tools have been attempted for that question.
- When mentioning facts or data from web results, include 1-2 source URLs.
- If WebSearchTool() is unavailable, say: "I cannot use the web search tool right now, so I must stop here."

5. Response Structure
- Always respond in this order:
  1) One line of empathy (brief summary of the user's situation)
  2) 2-4 key recommendations (short and clear)
  3) One action the user can do immediately
  4) One closing line of encouragement
- Use concrete action statements, not abstract advice.
- Keep it concise and checklist-friendly when possible.

6. Safety Guide
- For high-risk topics (medical, legal, financial), provide only general information and recommend consulting a qualified professional.
- If there are signs of self-harm or harm to others, prioritize immediate safety guidance and encourage professional crisis support.

MUST ANSWER IN KOREAN
"""

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach Agent",
        instructions=instruction,
        model="gpt-4o-mini",
        model_settings=ModelSettings(tool_choice="required"),
        tools=[
            WebSearchTool(),
            FileSearchTool(
                vector_store_ids=[
                    VECTOR_STORE_ID
                ],
                max_num_results=3
            )
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
        "response.file_search_call.completed": ("✅ File search completed.", "complete",),
        "response.file_search_call.in_progress": ("🗂️ Starting file search...", "running",),
        "response.file_search_call.searching": ("🗂️ File search in progress...", "running",),
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


prompt = st.chat_input(
    "Write a message for your assistant"
    , accept_file=True,
    file_type=["txt"]
)

if prompt:
    for file in prompt.files:
        if file.type.startswith("text/"):
            with st.chat_message("ai"):
                with st.status("⏳ Uploading file...") as status:
                    uploaded_file = client.files.create(
                        file=(file.name, file.getvalue()),
                        purpose="user_data"
                    )

                    status.update(label="⏳ Attaching file...")
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id
                    )
                    status.update(label="✅ File uploaded", state="complete")

    if prompt.text:
        with st.chat_message("human"):
            st.write(prompt.text)

        asyncio.run(run_agent(prompt.text))

with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
