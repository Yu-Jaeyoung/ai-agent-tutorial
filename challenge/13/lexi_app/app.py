from __future__ import annotations

import os
from typing import Any

import streamlit as st

from .service import AssistantTurnPayload, build_graph, run_turn, summarize_turn_result
from .state import LearningState, VocabularyEntry


CHAT_MESSAGES_SESSION_KEY = "chat_messages"
LEARNING_STATE_SESSION_KEY = "learning_state"
GRAPH_SESSION_KEY = "graph"
APP_READY_SESSION_KEY = "app_ready"
WELCOME_MESSAGE = (
    "영어 기술 문장, 영어 기술 용어, 또는 `review`를 입력해 주세요.\n\n"
    "LeXi가 문맥 기반 단어 카드 생성과 저장 기반 복습을 도와드립니다."
)


def load_runtime_secrets() -> None:
    if os.getenv("GOOGLE_API_KEY"):
        return

    try:
        secret = st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        return

    if secret:
        os.environ["GOOGLE_API_KEY"] = str(secret)


def get_chat_messages() -> list[dict[str, str]]:
    return st.session_state.setdefault(CHAT_MESSAGES_SESSION_KEY, [])


def append_chat_message(role: str, content: str) -> None:
    get_chat_messages().append({"role": role, "content": content})


def set_learning_state(state: LearningState | None) -> None:
    st.session_state[LEARNING_STATE_SESSION_KEY] = state


def get_learning_state() -> LearningState | None:
    return st.session_state.get(LEARNING_STATE_SESSION_KEY)


def reset_session() -> None:
    st.session_state[CHAT_MESSAGES_SESSION_KEY] = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    st.session_state[LEARNING_STATE_SESSION_KEY] = None


def ensure_app_state() -> None:
    if st.session_state.get(APP_READY_SESSION_KEY):
        return

    st.session_state[GRAPH_SESSION_KEY] = build_graph()
    st.session_state[APP_READY_SESSION_KEY] = True
    if not get_chat_messages():
        reset_session()


def format_entry(entry: VocabularyEntry, index: int) -> str:
    return (
        f"{index}. **{entry['word']}** (`{entry['lemma']}`)\n"
        f"- 뜻: {entry['meaning_in_context']}\n"
        f"- 문장: {entry['source_sentence']}\n"
        f"- 설명: {entry['context_note']}\n"
        f"- 왜 중요한가: {entry['why_it_matters']}\n"
        f"- 우선순위: {entry['study_priority']}"
    )


def format_learning_message(payload: AssistantTurnPayload) -> str:
    entries = payload.vocabulary_entries
    if not entries:
        return payload.assistant_text or "학습 결과를 생성하지 못했습니다."

    intro = payload.assistant_text
    if not intro:
        if payload.route == "single_term":
            intro = "입력한 기술 용어를 학습 카드로 정리했어요."
        else:
            intro = "이 입력에서 학습 가치가 높은 표현을 정리했어요."

    lines = [intro, ""]
    lines.extend(format_entry(entry, index) for index, entry in enumerate(entries, start=1))
    return "\n\n".join(lines)


def format_payload(payload: AssistantTurnPayload) -> str:
    if payload.mode == "learning":
        return format_learning_message(payload)
    return payload.assistant_text or "처리 결과가 없습니다."


def render_chat_history() -> None:
    for message in get_chat_messages():
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_user_input(user_text: str) -> None:
    append_chat_message("user", user_text)
    with st.chat_message("user"):
        st.markdown(user_text)

    try:
        next_state = run_turn(get_learning_state(), user_text)
        payload = summarize_turn_result(next_state)
        assistant_text = format_payload(payload)
        set_learning_state(next_state)
    except Exception as exc:
        assistant_text = f"요청 처리 중 오류가 발생했습니다.\n\n{exc}"

    append_chat_message("assistant", assistant_text)
    with st.chat_message("assistant"):
        st.markdown(assistant_text)


def main() -> None:
    load_runtime_secrets()
    st.set_page_config(page_title="LeXi", page_icon="L")
    ensure_app_state()

    st.title("LeXi")
    st.caption("영어 기술 문장을 학습 카드로 정리하고, 저장한 단어를 복습하는 Streamlit 학습 에이전트")

    render_chat_history()

    prompt = st.chat_input("영어 기술 문장, 기술 용어, 또는 review를 입력해 주세요.")
    if prompt:
        handle_user_input(prompt.strip())
