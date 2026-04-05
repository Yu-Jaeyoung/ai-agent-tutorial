from __future__ import annotations

import os

import streamlit as st

from .memory import list_users, load_memory_records
from .service import AssistantTurnPayload, build_graph, run_turn, summarize_turn_result
from .state import LearningState, VocabularyEntry


CHAT_MESSAGES_SESSION_KEY = "chat_messages"
LEARNING_STATE_SESSION_KEY = "learning_state"
GRAPH_SESSION_KEY = "graph"
APP_READY_SESSION_KEY = "app_ready"
PROCESSING_SESSION_KEY = "is_processing"
PENDING_INPUT_SESSION_KEY = "pending_input"
USER_ID_SESSION_KEY = "user_id"
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


def get_user_id() -> str | None:
    return st.session_state.get(USER_ID_SESSION_KEY)


def set_user_id(user_id: str) -> None:
    st.session_state[USER_ID_SESSION_KEY] = user_id


def get_chat_messages() -> list[dict[str, str]]:
    return st.session_state.setdefault(CHAT_MESSAGES_SESSION_KEY, [])


def append_chat_message(role: str, content: str) -> None:
    get_chat_messages().append({"role": role, "content": content})


def set_learning_state(state: LearningState | None) -> None:
    st.session_state[LEARNING_STATE_SESSION_KEY] = state


def get_learning_state() -> LearningState | None:
    return st.session_state.get(LEARNING_STATE_SESSION_KEY)


def is_processing() -> bool:
    return st.session_state.get(PROCESSING_SESSION_KEY, False)


def set_processing(value: bool) -> None:
    st.session_state[PROCESSING_SESSION_KEY] = value


def get_pending_input() -> str | None:
    return st.session_state.get(PENDING_INPUT_SESSION_KEY)


def set_pending_input(value: str | None) -> None:
    st.session_state[PENDING_INPUT_SESSION_KEY] = value


def reset_session() -> None:
    st.session_state[CHAT_MESSAGES_SESSION_KEY] = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    st.session_state[LEARNING_STATE_SESSION_KEY] = None
    st.session_state[PROCESSING_SESSION_KEY] = False
    st.session_state[PENDING_INPUT_SESSION_KEY] = None


def logout_user() -> None:
    reset_session()
    st.session_state.pop(USER_ID_SESSION_KEY, None)


def check_llm_connectivity() -> bool:
    if st.session_state.get("llm_check_passed"):
        return True
    try:
        from .config import get_llm
        get_llm().invoke("Say OK")
        st.session_state["llm_check_passed"] = True
        return True
    except Exception as exc:
        st.error(f"LLM 연결에 실패했습니다. GOOGLE_API_KEY를 확인해 주세요.\n\n`{type(exc).__name__}: {exc}`")
        return False


def ensure_app_state() -> bool:
    if st.session_state.get(APP_READY_SESSION_KEY):
        return True

    if not check_llm_connectivity():
        return False

    st.session_state[GRAPH_SESSION_KEY] = build_graph()
    st.session_state[APP_READY_SESSION_KEY] = True
    if not get_chat_messages():
        reset_session()
    return True


def render_user_select() -> bool:
    st.title("LeXi")
    st.caption("영어 기술 문장을 학습 카드로 정리하고, 저장한 단어를 복습하는 Streamlit 학습 에이전트")

    existing_users = list_users()

    tab_existing, tab_new = st.tabs(["기존 사용자", "새 사용자"])

    with tab_existing:
        if existing_users:
            selected = st.selectbox("사용자를 선택해 주세요.", existing_users, index=None, placeholder="선택...")
            if st.button("시작하기", key="btn_existing", disabled=not selected, use_container_width=True):
                set_user_id(selected)
                reset_session()
                st.rerun()
        else:
            st.info("아직 등록된 사용자가 없습니다. 새 사용자로 시작해 주세요.")

    with tab_new:
        new_name = st.text_input("사용자 이름을 입력해 주세요.", placeholder="예: jaeyoung")
        if st.button("등록 후 시작", key="btn_new", disabled=not new_name, use_container_width=True):
            name = new_name.strip()
            if name:
                set_user_id(name)
                reset_session()
                st.rerun()

    return False


def render_sidebar() -> None:
    user_id = get_user_id()
    state = get_learning_state()
    memory_records = load_memory_records(user_id) if user_id else []
    review_state = state.get("review_state") if state else None
    review_queue_length = len(state.get("review_queue", [])) if state else 0

    with st.sidebar:
        st.header("Session")
        st.caption(f"사용자: **{user_id}**")
        st.metric("Saved memory", len(memory_records))
        st.metric("Review active", "Yes" if review_state else "No")
        st.metric("Review queue", review_queue_length)
        if st.button("Reset Session", use_container_width=True):
            reset_session()
            st.rerun()
        if st.button("사용자 전환", use_container_width=True):
            logout_user()
            st.rerun()


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


def format_review_question(payload: AssistantTurnPayload) -> str:
    review_state = payload.review_state
    if not review_state:
        return payload.assistant_text or "복습 문제를 준비하지 못했습니다."

    return "\n\n".join(
        [
            "복습 문제를 준비했어요.",
            f"**단어**: `{review_state['current_word']}`",
            "**문장**:",
            f"> {review_state['current_source_sentence']}",
            "이 문맥에서 이 단어의 한국어 뜻을 입력해 주세요.",
        ]
    )


def format_review_feedback(payload: AssistantTurnPayload) -> str:
    latest = payload.latest_review_item
    if not latest:
        return payload.assistant_text or "복습 결과를 정리하지 못했습니다."

    is_correct = latest["judgment"] == "correct"
    title = "맞았어요." if is_correct else "조금 아쉬워요."
    explanation = latest.get("explanation", "").strip()
    lines = [title]

    if is_correct:
        lines.append(f"정답은 **{latest['expected_meaning']}** 입니다.")
        if explanation and explanation != "정답입니다. 현재 문맥에서의 의미를 정확히 이해했습니다.":
            lines.append(explanation)
    else:
        lines.append(f"내 답변: **{latest['user_answer']}**")
        lines.append(f"정답: **{latest['expected_meaning']}**")
        if explanation:
            lines.append(explanation)

    if payload.assistant_text:
        lines.append(payload.assistant_text)

    return "\n\n".join(lines)


def format_payload(payload: AssistantTurnPayload) -> str:
    if payload.mode == "learning":
        return format_learning_message(payload)
    if payload.mode == "review_question":
        return format_review_question(payload)
    if payload.mode == "review_feedback":
        return format_review_feedback(payload)
    return payload.assistant_text or "처리 결과가 없습니다."


def get_processing_message(user_text: str, previous_state: LearningState | None) -> str:
    normalized = user_text.strip().lower()
    if normalized == "review" or "review" in normalized or "복습" in user_text or "퀴즈" in user_text:
        return "복습할 단어와 문제를 준비하고 있어요..."
    if previous_state and previous_state.get("review_state"):
        return "답변을 확인하고 복습 결과를 정리하고 있어요..."
    return "문장과 기술 용어를 분석하고 학습 카드를 만들고 있어요..."


def render_chat_history() -> None:
    for message in get_chat_messages():
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_user_input(user_text: str) -> None:
    user_id = get_user_id() or "default"
    previous_state = get_learning_state()
    append_chat_message("user", user_text)
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        processing_message = get_processing_message(user_text, previous_state)
        status_placeholder.info(processing_message)

        try:
            with st.spinner("잠시만요. 처리 중입니다..."):
                next_state = run_turn(previous_state, user_text, user_id=user_id)
                payload = summarize_turn_result(next_state)
                assistant_text = format_payload(payload)
                set_learning_state(next_state)
        except RuntimeError as exc:
            assistant_text = f"설정 오류가 발생했습니다: {exc}"
        except Exception as exc:
            assistant_text = f"요청 처리 중 예상치 못한 오류가 발생했습니다.\n\n`{type(exc).__name__}: {exc}`"
        finally:
            set_processing(False)
            set_pending_input(None)

        status_placeholder.empty()
        st.markdown(assistant_text)

    append_chat_message("assistant", assistant_text)
    st.rerun()


def main() -> None:
    load_runtime_secrets()
    st.set_page_config(page_title="LeXi", page_icon="L")

    if not ensure_app_state():
        st.stop()

    if not get_user_id():
        render_user_select()
        return

    st.title("LeXi")
    st.caption("영어 기술 문장을 학습 카드로 정리하고, 저장한 단어를 복습하는 Streamlit 학습 에이전트")
    render_sidebar()

    render_chat_history()

    prompt = st.chat_input(
        "영어 기술 문장, 기술 용어, 또는 review를 입력해 주세요.",
        disabled=is_processing(),
    )

    if prompt and not is_processing():
        set_pending_input(prompt.strip())
        set_processing(True)
        st.rerun()

    pending_input = get_pending_input()
    if pending_input and is_processing():
        handle_user_input(pending_input)
