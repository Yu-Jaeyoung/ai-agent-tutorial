import base64

import dotenv
import asyncio
import os
import streamlit as st
from openai import OpenAI
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool, ModelSettings, ImageGenerationTool

dotenv.load_dotenv()

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

client = OpenAI()

goal_extractor_instruction = """
1. Role
You are a Goal Extraction Assistant.
Your sole responsibility is to identify and structure the user's goal from uploaded files and user input.

2. Required Tool Usage
- You MUST use FileSearchTool() to search the uploaded files for evidence.
- Extract the user's goal, current situation, constraints, and preferences based on file evidence.
- If no relevant evidence is found in the files, explicitly state: "No relevant file evidence found."

3. Output Format
- Return the result in the following exact structure (all section content in Korean):

  [GOAL]
  ...

  [CURRENT_SITUATION]
  ...

  [CONSTRAINTS_AND_PREFERENCES]
  ...

  [KEY_SUMMARY]
  ...

  [IMAGE_GENERATION]
  YES or NO

  [IMAGE_GENERATION_REASON]
  - GOAL_ACHIEVED: The user indicates they have achieved, completed, or succeeded in their goal.
  - USER_REQUEST: The user explicitly requests image generation.
  - NONE: Not applicable.

  [IMAGE_PROMPT]
  (Only if IMAGE_GENERATION is YES)
  - For GOAL_ACHIEVED: "Celebratory image for achieving the goal of {goal description}. Joyful, vibrant, congratulatory scene."
  - For USER_REQUEST: An English image prompt based on the user's request.

4. Image Generation Decision Rules
- The user's input may be in Korean. You must also detect Korean achievement expressions such as: 달성했어, 성공했어, 해냈어, 완료했어, 끝냈어, 이뤘어, etc.
- If the user's message contains achievement-related expressions (in any language) regarding their goal → YES / GOAL_ACHIEVED
- If the user explicitly requests an image or visual (e.g., 이미지 만들어줘, 그림 그려줘, generate an image) → YES / USER_REQUEST
- Otherwise → NO / NONE

5. Important
- Keep the output concise and factual.
- Section content (descriptions, summaries) MUST be written in Korean.
"""

web_research_instruction = """
1. Role
You are a Web Research Assistant for life coaching.
Your responsibility is to find up-to-date, evidence-based information to help the user achieve their goal.

2. Required Tool Usage
- You MUST use WebSearchTool() to search for current information.
- Search for practical methods, routines, habits, and evidence-based tips relevant to the user's goal.
- Include 1-2 source URLs for any factual claims.
- If WebSearchTool() is unavailable or fails, respond with: "Web search tool is currently unavailable. Cannot proceed."

3. Output Format
- Return the result in the following exact structure (all section content in Korean):

  [SEARCH_KEYWORDS]
  ...

  [EVIDENCE_SUMMARY]
  - ...

  [RECOMMENDED_METHODS]
  - ...

  [SOURCES]
  - ...

4. Important
- Focus on actionable and recent information (within the last 1-2 years if possible).
- Section content MUST be written in Korean.
"""

final_coach_instruction = """
1. Role
You are a warm, encouraging, and professional Life Coach.
You synthesize goal analysis and web research to provide personalized coaching.

2. Input Context
You will receive:
  a) The user's question
  b) A file-based goal summary (from Goal Extractor Agent)
  c) A web-based research summary (from Web Research Agent)
You MUST ground your recommendations in this context.

3. Tone & Style
- Be warm, respectful, and supportive.
- Acknowledge the user's feelings and effort before giving advice.
- Never criticize, make absolute judgments, or overpromise.
- Use concrete, actionable statements instead of vague or abstract advice.

4. Response Structure
Always respond in this order:
  1) Empathy statement: A brief one-line summary acknowledging the user's situation.
  2) Personalized recommendations: 2-4 specific, actionable recommendations.
  3) Immediate action: One thing the user can do right now.
  4) Encouragement: One closing line of motivation.
- Use bullet points or checklists when possible for clarity.

5. Safety Guidelines
- For high-risk topics (medical, legal, financial): Provide only general information and strongly recommend consulting a qualified professional.
- If there are signs of self-harm or harm to others: Prioritize immediate safety guidance and encourage professional crisis support.

6. Language Requirement (CRITICAL)
- You MUST ALWAYS respond entirely in Korean (한국어).
- This is non-negotiable regardless of the input language.
- Every single word of your response must be in Korean.
"""

image_generation_instruction = """
1. Role
You are a Creative Image Generation Assistant.

2. Input
- You will receive an image prompt under the [IMAGE_PROMPT] tag.
- Use the prompt exactly as provided.

3. Required Tool Usage
- You MUST call ImageGenerationTool() with the provided prompt to generate the image.
- Do NOT describe the image in text. Only generate it using the tool.
- Do NOT modify or translate the prompt unless it contains harmful content.
"""

if "goal_agent" not in st.session_state:
    st.session_state["goal_agent"] = Agent(
        name="Goal Extractor Agent",
        instructions=goal_extractor_instruction,
        model="gpt-4o-mini",
        model_settings=ModelSettings(tool_choice="required"),
        tools=[
            FileSearchTool(
                vector_store_ids=[
                    VECTOR_STORE_ID
                ],
                max_num_results=3
            )
        ]
    )

if "web_agent" not in st.session_state:
    st.session_state["web_agent"] = Agent(
        name="Web Research Agent",
        instructions=web_research_instruction,
        model="gpt-4o-mini",
        model_settings=ModelSettings(tool_choice="required"),
        tools=[
            WebSearchTool()
        ]
    )

if "image_generation_agent" not in st.session_state:
    st.session_state["image_generation_agent"] = Agent(
        name="Image Generation Agent",
        instructions=image_generation_instruction,
        model="gpt-4o-mini",
        model_settings=ModelSettings(tool_choice="required"),
        tools=[
            ImageGenerationTool(
                tool_config={
                    "type": "image_generation",
                    "quality": "medium",
                    "output_format": "jpeg",
                    "moderation": "low",
                    "partial_images": 1
                }
            )
        ]
    )

if "final_coach_agent" not in st.session_state:
    st.session_state["final_coach_agent"] = Agent(
        name="Final Coach Agent",
        instructions=final_coach_instruction,
        model="gpt-4o-mini",
    )

goal_agent = st.session_state["goal_agent"]
web_agent = st.session_state["web_agent"]
image_generation_agent = st.session_state["image_generation_agent"]
final_coach_agent = st.session_state["final_coach_agent"]

if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history",
        "chat-gpt-clone-memory-db"
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
                        for content in message["content"]:
                            if content.get("type") == "text":
                                st.write(content["text"])
                            elif content.get("type") == "image_generation_call":
                                image_data = base64.b64decode(content["result"])
                                st.image(image_data, caption="🎨 당신을 위한 동기부여 이미지", use_container_width=True)


def parse_image_prompt(goal_context: str) -> str:
    fallback = (
        "A motivational vision board with vibrant and inspiring visuals "
        "representing personal growth, goals, and achievement. "
        "Colorful, uplifting, and energetic atmosphere."
    )

    if "[IMAGE_PROMPT]" not in goal_context:
        return fallback

    try:
        after_tag = goal_context.split("[IMAGE_PROMPT]")[1]
        next_tag_index = after_tag.find("[")
        if next_tag_index != -1:
            prompt_text = after_tag[:next_tag_index].strip()
        else:
            prompt_text = after_tag.strip()

        for prefix in ["- GOAL_ACHIEVED:", "- USER_REQUEST:", "GOAL_ACHIEVED:", "USER_REQUEST:"]:
            if prompt_text.startswith(prefix):
                prompt_text = prompt_text[len(prefix):].strip()

        prompt_text = prompt_text.strip('"').strip("'")

        return prompt_text if prompt_text else fallback

    except Exception:
        return fallback


def should_generate_image(goal_context: str) -> bool:
    """Check if the goal extractor decided image generation is needed."""
    if "[IMAGE_GENERATION]" not in goal_context:
        return False
    try:
        after_tag = goal_context.split("[IMAGE_GENERATION]")[1]
        next_tag_index = after_tag.find("[")
        if next_tag_index != -1:
            value = after_tag[:next_tag_index].strip()
        else:
            value = after_tag.strip()
        return value.upper().startswith("YES")
    except Exception:
        return False


def update_status(status_container, event_type, phase):
    phase_status_messages = {
        "file": {
            "response.file_search_call.in_progress": ("🗂️ 목표 파일 검색 중...", "running"),
            "response.file_search_call.searching": ("🗂️ 목표 파일 검색 중...", "running"),
            "response.file_search_call.completed": ("✅ 파일 검색 완료", "complete"),
        },
        "web": {
            "response.web_search_call.in_progress": ("🔍 웹 검색 시작...", "running"),
            "response.web_search_call.searching": ("🔍 목표 달성 방법 검색 중...", "running"),
            "response.web_search_call.completed": ("✅ 웹 검색 완료", "complete"),
        },
        "final": {
            "response.completed": ("✅ 코칭 응답 준비 완료", "complete"),
        },
        "image": {
            "response.image_generation_call.in_progress": ("🎨 이미지 생성 중...", "running"),
            "response.image_generation_call.completed": ("✅ 이미지 생성 완료", "complete"),
        },
    }

    phase_messages = phase_status_messages.get(phase, {})
    if event_type in phase_messages:
        label, state = phase_messages[event_type]
        status_container.update(label=label, state=state)


asyncio.run(paint_history())


async def run_agent(message):
    with st.chat_message("ai"):
        # Phase 1: Goal Extraction
        file_status = st.status("🗂️ 목표 파일 검색 중...", expanded=False)
        goal_context = ""

        goal_stream = Runner.run_streamed(
            goal_agent,
            f"User question: {message}",
        )

        async for event in goal_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(file_status, event.data.type, "file")

                if event.data.type == "response.output_text.delta":
                    goal_context += event.data.delta

        goal_context = goal_context.strip() if goal_context.strip() else "No relevant goal information found in files."
        file_status.update(label="✅ 목표 파일 검색 완료", state="complete")

        # Phase 2: Web Research
        web_status = st.status("🔍 목표 달성 방법 웹 검색 중...", expanded=False)
        web_context = ""

        web_stream = Runner.run_streamed(
            web_agent,
            "Research information needed to achieve the user's goal based on the following.\n\n"
            f"[USER_QUESTION]\n{message}\n\n"
            f"[FILE_BASED_GOAL_SUMMARY]\n{goal_context}",
        )

        async for event in web_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(web_status, event.data.type, "web")

                if event.data.type == "response.output_text.delta":
                    web_context += event.data.delta

        web_context = web_context.strip() if web_context.strip() else "Could not summarize web search results."
        web_status.update(label="✅ 웹 검색 완료", state="complete")

        # Phase 3: Final Coaching Response
        final_status = st.status("🧭 맞춤형 코칭 준비 중...", expanded=False)
        response = ""
        text_placeholder = st.empty()

        final_stream = Runner.run_streamed(
            final_coach_agent,
            "Provide a personalized coaching response based on the information below.\n\n"
            f"[USER_QUESTION]\n{message}\n\n"
            f"[FILE_BASED_GOAL_SUMMARY]\n{goal_context}\n\n"
            f"[WEB_RESEARCH_SUMMARY]\n{web_context}\n\n"
            "IMPORTANT: Your entire response MUST be in Korean.",
            session=session
        )

        async for event in final_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(final_status, event.data.type, "final")

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)

        final_status.update(label="✅ 코칭 응답 준비 완료", state="complete")

        # Phase 4: Image Generation (conditional)
        if should_generate_image(goal_context):
            image_prompt = parse_image_prompt(goal_context)
            image_status = st.status("🎨 동기부여 이미지 생성 중...", expanded=False)

            image_stream = Runner.run_streamed(
                image_generation_agent,
                f"[IMAGE_PROMPT]\n{image_prompt}\n\n"
                f"[USER_GOAL_SUMMARY]\n{goal_context[:500]}"
            )

            async for event in image_stream.stream_events():
                if event.type == "raw_response_event":
                    update_status(image_status, event.data.type, "image")

            image_rendered = False
            for item in image_stream.raw_responses:
                if image_rendered:
                    break
                for output in item.output:
                    if output.type == "image_generation_call":
                        image_data = base64.b64decode(output.result)
                        st.image(image_data, caption="🎨 당신을 위한 동기부여 이미지", use_container_width=True)
                        image_rendered = True
                        break

            image_status.update(label="✅ 이미지 생성 완료", state="complete")


prompt = st.chat_input(
    "코치에게 메시지를 입력하세요",
    accept_file="multiple",
    file_type=["txt"]
)

if prompt:
    if hasattr(prompt, "files") and prompt.files:
        for file in prompt.files:
            if file.type.startswith("text/"):
                with st.chat_message("ai"):
                    with st.status("⏳ 파일 업로드 중...") as status:
                        uploaded_file = client.files.create(
                            file=(file.name, file.getvalue()),
                            purpose="user_data"
                        )

                        status.update(label="⏳ 파일 첨부 중...")
                        client.vector_stores.files.create(
                            vector_store_id=VECTOR_STORE_ID,
                            file_id=uploaded_file.id
                        )
                        status.update(label="✅ 파일 업로드 완료", state="complete")

    user_text = prompt.text if hasattr(prompt, "text") else str(prompt)
    if user_text:
        with st.chat_message("human"):
            st.write(user_text)

        asyncio.run(run_agent(user_text))

with st.sidebar:
    reset = st.button("메모리 초기화")
    if reset:
        asyncio.run(session.clear_session())
