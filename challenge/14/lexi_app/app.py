from __future__ import annotations

import os
import random
import threading
import time

import streamlit as st

from .memory import list_users, load_memory_records
from .service import AssistantTurnPayload, build_graph, run_turn, summarize_turn_result
from .state import LearningState, MemoryRecord, VocabularyEntry


CHAT_MESSAGES_SESSION_KEY = "chat_messages"
LEARNING_STATE_SESSION_KEY = "learning_state"
GRAPH_SESSION_KEY = "graph"
APP_READY_SESSION_KEY = "app_ready"
PROCESSING_SESSION_KEY = "is_processing"
PENDING_INPUT_SESSION_KEY = "pending_input"
USER_ID_SESSION_KEY = "user_id"
MAX_CHAT_MESSAGES = 100
LOADING_TIP_INTERVAL = 3.0
WELCOME_MESSAGE = (
    "LeXi에 오신 것을 환영합니다.\n\n"
    "**사용 방법:**\n"
    "1. **영어 기술 문장 입력** - 문장에서 핵심 용어를 추출해 학습 카드를 만듭니다.\n"
    "2. **영어 기술 용어 입력** - 해당 용어의 문맥 기반 학습 카드를 생성합니다.\n"
    "3. **`review` 입력** - 저장된 단어를 복습합니다.\n\n"
    "아래 입력창에 영어 기술 문장이나 용어를 입력해 시작하세요."
)

GENERAL_TIPS = [
    "기술 문서를 읽을 때 모르는 단어를 바로 입력하면 학습 효과가 높아요.",
    "같은 단어도 문맥에 따라 뜻이 달라질 수 있어요. 다양한 문장으로 학습해 보세요.",
    "복습은 짧은 간격으로 자주 하는 것이 장기 기억에 효과적이에요.",
    "하루에 3-5개 단어를 꾸준히 학습하면 한 달에 100개 이상의 단어를 익힐 수 있어요.",
    "기술 용어는 원래 의미(어원)를 알면 파생 용어도 쉽게 이해할 수 있어요.",
    "영어 기술 블로그를 읽으면서 모르는 문장을 LeXi에 넣어보세요.",
    "학습 카드의 '왜 중요한가' 항목을 읽으면 실제 활용 맥락을 파악하는 데 도움이 돼요.",
    "review를 반복하면 틀린 단어가 우선 출제돼요. 약한 부분을 집중 보강할 수 있어요.",
]

TECH_TERM_TIPS = [
    ("Latency", "요청을 보낸 뒤 응답을 받기까지 걸리는 시간. 네트워크와 시스템 성능의 핵심 지표예요."),
    ("Throughput", "단위 시간당 처리할 수 있는 작업의 양. Latency와 함께 성능을 측정하는 양대 지표예요."),
    ("Idempotent", "같은 요청을 여러 번 보내도 결과가 동일한 성질. API 설계에서 중요한 개념이에요."),
    ("Serialization", "데이터를 저장하거나 전송할 수 있는 형식으로 변환하는 과정이에요."),
    ("Middleware", "요청과 응답 사이에서 공통 처리를 담당하는 소프트웨어 계층이에요."),
    ("Concurrency", "여러 작업이 동시에 진행되는 것처럼 보이게 하는 프로그래밍 기법이에요."),
    ("Pagination", "대량의 데이터를 페이지 단위로 나누어 전달하는 방식이에요."),
    ("Rate Limiting", "일정 시간 내 요청 수를 제한하여 서비스를 보호하는 기법이에요."),
    ("Eventual Consistency", "분산 시스템에서 시간이 지나면 모든 노드가 같은 상태에 도달하는 모델이에요."),
    ("Backpressure", "처리 속도를 초과하는 데이터 흐름을 조절하는 메커니즘이에요."),
]


def _build_loading_messages(memory_records: list[MemoryRecord]) -> list[str]:
    messages: list[str] = []

    for tip in GENERAL_TIPS:
        messages.append(tip)

    for term, desc in TECH_TERM_TIPS:
        messages.append(f"**오늘의 용어: {term}** — {desc}")

    if memory_records:
        sampled = random.sample(memory_records, min(5, len(memory_records)))
        for record in sampled:
            messages.append(
                f"**단어장 복습: {record['word']}** — {record['meaning_in_context']}"
            )

    random.shuffle(messages)
    return messages


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
    messages = get_chat_messages()
    messages.append({"role": role, "content": content})
    if len(messages) > MAX_CHAT_MESSAGES:
        st.session_state[CHAT_MESSAGES_SESSION_KEY] = [messages[0]] + messages[-(MAX_CHAT_MESSAGES - 1):]


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


def render_user_select() -> None:
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


def render_sidebar() -> None:
    user_id = get_user_id()
    state = get_learning_state()
    memory_records = load_memory_records(user_id) if user_id else []
    review_state = state.get("review_state") if state else None
    review_queue_length = len(state.get("review_queue", [])) if state else 0

    with st.sidebar:
        st.header("LeXi 대시보드")
        st.caption(f"사용자: **{user_id}**")
        st.metric("저장된 단어", len(memory_records))
        st.metric("복습 진행 중", "예" if review_state else "아니오")
        st.metric("남은 복습 문제", review_queue_length)

        if memory_records:
            with st.expander("단어장 보기", expanded=False):
                for record in memory_records[:10]:
                    st.markdown(f"- **{record['word']}**: {record['meaning_in_context']}")
                if len(memory_records) > 10:
                    st.caption(f"외 {len(memory_records) - 10}개")

        if st.button("세션 초기화", use_container_width=True):
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


def get_processing_label(user_text: str, previous_state: LearningState | None) -> str:
    normalized = user_text.strip().lower()
    if normalized == "review" or "review" in normalized or "복습" in user_text or "퀴즈" in user_text:
        return "복습 준비 중..."
    if previous_state and previous_state.get("review_state"):
        return "답변 확인 중..."
    return "학습 카드 생성 중..."


def render_chat_history() -> None:
    for message in get_chat_messages():
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_user_input(user_text: str) -> None:
    user_id = get_user_id() or "default"
    previous_state = get_learning_state()
    memory_records = load_memory_records(user_id)
    loading_messages = _build_loading_messages(memory_records)

    append_chat_message("user", user_text)
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        label = get_processing_label(user_text, previous_state)
        tip_placeholder = st.empty()
        status_placeholder = st.empty()

        result_box: dict = {}
        done_event = threading.Event()

        def _run():
            try:
                result_box["state"] = run_turn(previous_state, user_text, user_id=user_id)
            except Exception as exc:
                result_box["error"] = exc
            finally:
                done_event.set()

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        tip_idx = 0
        status_placeholder.info(f"**{label}**")
        while not done_event.is_set():
            if loading_messages:
                tip_placeholder.markdown(
                    f"*{loading_messages[tip_idx % len(loading_messages)]}*"
                )
                tip_idx += 1
            done_event.wait(timeout=LOADING_TIP_INTERVAL)

        worker.join()
        tip_placeholder.empty()
        status_placeholder.empty()

        try:
            if "error" in result_box:
                raise result_box["error"]
            next_state = result_box["state"]
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
