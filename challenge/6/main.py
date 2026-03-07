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
You are a goal extraction assistant.

2. Required Tool Usage
- You must use FileSearchTool() to search uploaded files.
- Identify the user's goal, current situation, constraints, and preferences from file evidence.
- If no relevant file evidence exists, clearly say so.

3. Output Format
- Return Korean text in this exact structure:
  [목표]
  ...[현재 상황]
  ...

  [제약/선호]
  ...

  [핵심 요약]
  ...

  [이미지 생성 여부]
  YES 또는 NO

  [이미지 생성 사유]
  - GOAL_ACHIEVED: 사용자가 목표를 달성했다는 내용이 있을 때
  - USER_REQUEST: 사용자가 직접 이미지 생성을 요청했을 때
  - NONE: 해당 없음

  [이미지 프롬프트]
  (이미지 생성이 YES인 경우에만 작성)
  - GOAL_ACHIEVED: "Celebratory image for achieving the goal of {목표 내용}. Joyful, vibrant, congratulatory scene."
  - USER_REQUEST: 사용자 요청 내용을 기반으로 한 영어 이미지 프롬프트

- Keep it concise and factual.

4. Image Generation Decision Rules
- If the user says they have "달성", "완료", "성공", "해냈", "이뤘" regarding their goal → YES / GOAL_ACHIEVED
- If the user explicitly requests an image or visual related to their goal → YES / USER_REQUEST
- Otherwise → NO / NONE
"""

web_research_instruction = """
1. Role
You are a web research assistant for coaching.

2. Required Tool Usage
- You must use WebSearchTool() to find up-to-date information that helps the user achieve their goal.
- Search practical methods, routines, and evidence-based tips.
- Include 1-2 source URLs when you mention facts.
- If WebSearchTool() is unavailable, say: "I cannot use the web search tool right now, so I must stop here."

3. Output Format
- Return Korean text in this exact structure:
  [웹 검색 키워드]
  ...

  [최신 근거 요약]
  - ...

  [목표 달성 방법]
  - ...

  [출처]
  - ...
"""

final_coach_instruction = """
1. Role
You are a kind and encouraging Life Coach.

2. Input Context Rule
- You will receive:
  a) User question
  b) File-based goal summary
  c) Web-based research summary
- You must provide personalized recommendations grounded in that context.

3. Tone
- Be warm, respectful, and supportive.
- Acknowledge the user's feelings and effort first.
- Do not criticize, make absolute judgments, or overpromise.
- Always answer kindly.

4. Response Structure
- Always respond in this order:
  1) One line of empathy (brief summary of the user's situation)
  2) 2-4 key personalized recommendations (short and clear)
  3) One action the user can do immediately
  4) One closing line of encouragement
- Use concrete action statements, not abstract advice.
- Keep it concise and checklist-friendly when possible.

5. Safety Guide
- For high-risk topics (medical, legal, financial), provide only general information and recommend consulting a qualified professional.
- If there are signs of self-harm or harm to others, prioritize immediate safety guidance and encourage professional crisis support.

MUST ANSWER IN KOREAN
"""

image_generation_instruction = """
1. Role
You are a creative image generation assistant.

2. Input Format
- You will receive an image prompt under the [이미지 프롬프트] tag.
- Use the prompt exactly as provided to generate the image.

3. Required Tool Usage
- You MUST call ImageGenerationTool() with the provided prompt.
- Do NOT describe the image in text. Only generate it using the tool.
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
                        for content in message["content"]:
                            if content.get("type") == "text":
                                st.write(content["text"])
                            elif content.get("type") == "image_generation_call":  # ✅ 이미지 복원 추가
                                image_data = base64.b64decode(content["result"])
                                st.image(image_data, caption="🎨 당신을 위한 동기부여 이미지", use_container_width=True)


def parse_image_prompt(goal_context: str) -> str:
    fallback = (
        "A motivational vision board with vibrant and inspiring visuals "
        "representing personal growth, goals, and achievement. "
        "Colorful, uplifting, and energetic atmosphere."
    )

    if "[이미지 프롬프트]" not in goal_context:
        return fallback

    try:
        after_tag = goal_context.split("[이미지 프롬프트]")[1]
        # 다음 섹션 태그가 나오기 전까지만 추출
        next_tag_index = after_tag.find("[")
        if next_tag_index != -1:
            prompt_text = after_tag[:next_tag_index].strip()
        else:
            prompt_text = after_tag.strip()

        # GOAL_ACHIEVED / USER_REQUEST 접두어 제거
        for prefix in ["- GOAL_ACHIEVED:", "- USER_REQUEST:", "GOAL_ACHIEVED:", "USER_REQUEST:"]:
            if prompt_text.startswith(prefix):
                prompt_text = prompt_text[len(prefix):].strip()

        # 따옴표 제거
        prompt_text = prompt_text.strip('"').strip("'")

        return prompt_text if prompt_text else fallback

    except Exception:
        return fallback


def update_status(status_container, event, phase):
    phase_status_messages = {
        "file": {
            "response.file_search_call.in_progress": ("🗂️ 목표 파일 검색 시작...", "running"),
            "response.file_search_call.searching": ("🗂️ 목표 파일 검색 중...", "running"),
            "response.file_search_call.completed": ("✅ 목표 파일 검색 완료", "complete"),
        },
        "web": {
            "response.web_search_call.in_progress": ("🔍 웹 검색 시작...", "running"),
            "response.web_search_call.searching": ("🔍 목표 달성 방법 검색 중...", "running"),
            "response.web_search_call.completed": ("✅ 웹 검색 완료", "complete"),
        },
        "final": {
            "response.completed": ("✅ 최종 답변 생성 완료", "complete"),
        },
        "image": {
            "response.image_generation_call.in_progress": ("🎨 이미지 생성 시작...", "running"),
            "response.image_generation_call.completed": ("✅ 이미지 생성 완료", "complete"),
        },
    }

    phase_messages = phase_status_messages.get(phase, {})
    if event in phase_messages:
        label, state = phase_messages[event]
        status_container.update(label=label, state=state)


asyncio.run(paint_history())


async def run_agent(message):
    with st.chat_message("ai"):
        file_status = st.status("🗂️ 목표 파일 검색 중...", expanded=False)
        goal_context = ""

        goal_stream = Runner.run_streamed(
            goal_agent,
            f"사용자 질문: {message}",
        )

        async for event in goal_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(file_status, event.data.type, "file")

                if event.data.type == "response.output_text.delta":
                    goal_context += event.data.delta

        goal_context = goal_context.strip() if goal_context.strip() else "파일에서 관련 목표 정보를 찾지 못했습니다."
        file_status.update(label="✅ 목표 파일 검색 및 정리 완료", state="complete")

        web_status = st.status("🔍 목표 달성 방법 웹 검색 중...", expanded=False)
        web_context = ""

        web_stream = Runner.run_streamed(
            web_agent,
            "사용자 질문을 바탕으로 목표 달성에 필요한 정보를 조사하세요.\n\n"
            f"[사용자 질문]\n{message}\n\n"
            f"[파일 기반 목표 요약]\n{goal_context}",
        )

        async for event in web_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(web_status, event.data.type, "web")

                if event.data.type == "response.output_text.delta":
                    web_context += event.data.delta

        web_context = web_context.strip() if web_context.strip() else "웹 검색 결과를 요약하지 못했습니다."
        web_status.update(label="✅ 웹 검색 및 정리 완료", state="complete")

        final_status = st.status("🧭 개인화 추천 정리 중...", expanded=False)
        response = ""
        text_placeholder = st.empty()

        final_stream = Runner.run_streamed(
            final_coach_agent,
            "아래 정보를 바탕으로 개인화 코칭 답변을 작성하세요.\n\n"
            f"[사용자 질문]\n{message}\n\n"
            f"[파일 기반 목표 요약]\n{goal_context}\n\n"
            f"[웹 검색 요약]\n{web_context}",
            session=session
        )

        async for event in final_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(final_status, event.data.type, "final")

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)

        final_status.update(label="✅ 개인화 코칭 답변 완료", state="complete")

        image_prompt = parse_image_prompt(goal_context)
        image_status = st.status("🎨 동기부여 이미지 생성 중...", expanded=False)

        image_stream = Runner.run_streamed(
            image_generation_agent,
            f"[이미지 프롬프트]\n{image_prompt}\n\n"
            f"[사용자 목표 요약]\n{goal_context[:500]}"
        )

        async for event in image_stream.stream_events():
            if event.type == "raw_response_event":
                update_status(image_status, event.data.type, "image")

        for item in image_stream.raw_responses:
            for output in item.output:
                if output.type == "image_generation_call":
                    image_data = base64.b64decode(output.result)
                    st.image(image_data, caption="🎨 당신을 위한 동기부여 이미지", use_container_width=True)
                    break

        image_status.update(label="✅ 이미지 생성 완료", state="complete")


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
