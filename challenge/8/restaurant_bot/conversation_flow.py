from __future__ import annotations

import re
from typing import Any

from .menu_catalog import get_menu_names, normalize_text
from .models import PendingFlowState, RestaurantRunContext

_FLOW_KIND_BY_AGENT = {
    "Menu Agent": "menu",
    "Order Agent": "order",
    "Reservation Agent": "reservation",
    "Complaints Agent": "complaints",
}

_ORDER_CONFIRMATION_PROMPTS = (
    "주문이맞는지확인해주시면결제단계로진행하겠습니다",
    "주문이맞는지확인해주시면",
    "결제단계로진행하겠습니다",
)

_ORDER_PAYMENT_METHOD_PROMPTS = (
    "결제수단을선택해주세요",
    "카드또는현장결제중에서선택할수있어요",
)

_ORDER_PAYMENT_CONFIRMATION_PROMPTS = (
    "카드결제를진행할까요",
    "확인해주시면결제를진행하겠습니다",
)

_ORDER_CARD_COMPLETION_PROMPTS = (
    "결제가완료되었습니다",
    "주문이접수되었습니다",
    "잠시만기다려주세요",
)

_ORDER_ONSITE_COMPLETION_PROMPTS = (
    "주문이완료되었습니다",
    "결제는매장에서진행됩니다",
)

_RESERVATION_CONFIRMATION_PROMPTS = (
    "예약 내용을 확인",
    "예약이 맞는지",
    "확인해주시면 진행",
)

_RESERVATION_COMPLETION_PROMPTS = (
    "예약이 완료되었습니다",
)

_CONFIRMATION_INPUTS = (
    "확인",
    "확인했어",
    "주문내용확인했어",
    "주문내용확인",
    "맞아",
    "맞아요",
    "맞습니다",
    "진행해줘",
    "진행해주세요",
    "주문해줘",
    "주문해주세요",
    "예약해줘",
    "예약해주세요",
    "그대로해줘",
    "그대로진행해줘",
)

_PAYMENT_METHOD_INPUTS = (
    "카드",
    "카드로할게",
    "카드로결제할게",
    "현장결제",
    "현장결제로할게",
    "매장에서결제할게",
    "매장결제",
)

_PAYMENT_CONFIRMATION_INPUTS = (
    "결제해줘",
    "결제진행해줘",
    "승인해줘",
    "결제해주세요",
    "결제진행해주세요",
)

_ORDER_FOLLOW_UP_KEYWORDS = (
    "추가",
    "빼줘",
    "빼",
    "제외",
    "변경",
    "수정",
    "그거",
    "그걸로",
    "이걸로",
    "수량",
)

_MENU_FOLLOW_UP_KEYWORDS = (
    "그거",
    "그메뉴",
    "알레르기",
    "채식",
    "비건",
    "재료",
    "가격",
    "추천",
    "맵기",
    "매운",
)

_COMPLAINT_FOLLOW_UP_KEYWORDS = (
    "매니저",
    "콜백",
    "환불",
    "할인",
    "보상",
    "검토",
    "연락",
)

_RESERVATION_FOLLOW_UP_KEYWORDS = (
    "예약해줘",
    "예약해주세요",
    "오늘",
    "내일",
    "모레",
    "오전",
    "오후",
    "시",
    "분",
    "명",
    "인",
)


def _mentions_known_menu(text: str) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(menu_name) in normalized for menu_name in get_menu_names())


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(keyword) in normalized for keyword in keywords)


def _looks_like_confirmation_input(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {normalize_text(candidate) for candidate in _CONFIRMATION_INPUTS}


def _looks_like_payment_method_input(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {normalize_text(candidate) for candidate in _PAYMENT_METHOD_INPUTS}


def _looks_like_payment_confirmation_input(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {normalize_text(candidate) for candidate in _PAYMENT_CONFIRMATION_INPUTS}


def _looks_like_order_follow_up(text: str) -> bool:
    normalized = normalize_text(text)
    if _contains_any_keyword(text, _ORDER_FOLLOW_UP_KEYWORDS):
        return True
    if _mentions_known_menu(text):
        return True
    if re.search(r"\d", text):
        return True
    return normalized in {"그거로", "그걸로", "이걸로", "저걸로"}


def _looks_like_reservation_follow_up(text: str) -> bool:
    stripped = text.strip()
    if _contains_any_keyword(text, _RESERVATION_FOLLOW_UP_KEYWORDS):
        return True
    if re.search(r"\d", stripped) and len(stripped) <= 20:
        return True
    if re.fullmatch(r"[가-힣]{2,4}", stripped):
        return True
    if re.fullmatch(r"[\d\-+ ]{8,20}", stripped):
        return True
    return False


def _looks_like_complaints_follow_up(text: str) -> bool:
    return _contains_any_keyword(text, _COMPLAINT_FOLLOW_UP_KEYWORDS)


def _looks_like_menu_follow_up(text: str) -> bool:
    return _contains_any_keyword(text, _MENU_FOLLOW_UP_KEYWORDS) or _mentions_known_menu(text)


def get_flow_kind_for_agent(agent_name: str | None) -> str | None:
    if agent_name is None:
        return None
    return _FLOW_KIND_BY_AGENT.get(agent_name)


def build_run_context(
    *,
    active_agent_name: str | None,
    latest_assistant_text: str,
    pending_flow_state: PendingFlowState | None,
) -> RestaurantRunContext:
    return RestaurantRunContext(
        active_agent_name=active_agent_name,
        latest_assistant_text=latest_assistant_text,
        pending_flow_state=pending_flow_state,
    )


def infer_pending_flow_state(
    *,
    agent_name: str,
    assistant_text: str,
) -> PendingFlowState | None:
    flow_kind = get_flow_kind_for_agent(agent_name)
    if flow_kind is None:
        return None

    normalized = normalize_text(assistant_text)
    if flow_kind == "order":
        if all(prompt in normalized for prompt in _ORDER_CARD_COMPLETION_PROMPTS) or all(
            prompt in normalized for prompt in _ORDER_ONSITE_COMPLETION_PROMPTS
        ):
            stage = "completed"
        elif any(prompt in normalized for prompt in _ORDER_PAYMENT_CONFIRMATION_PROMPTS):
            stage = "awaiting_payment_confirmation"
        elif any(prompt in normalized for prompt in _ORDER_PAYMENT_METHOD_PROMPTS):
            stage = "awaiting_payment_method"
        elif any(prompt in normalized for prompt in _ORDER_CONFIRMATION_PROMPTS):
            stage = "awaiting_confirmation"
        else:
            stage = "awaiting_details"
    elif flow_kind == "reservation":
        if any(normalize_text(prompt) in normalized for prompt in _RESERVATION_COMPLETION_PROMPTS):
            stage = "completed"
        elif any(normalize_text(prompt) in normalized for prompt in _RESERVATION_CONFIRMATION_PROMPTS):
            stage = "awaiting_confirmation"
        else:
            stage = "awaiting_details"
    else:
        stage = "awaiting_details"

    return PendingFlowState(
        agent_name=agent_name,
        flow_kind=flow_kind,
        stage=stage,
    )


def should_reset_to_triage(pending_flow_state: PendingFlowState | None) -> bool:
    if pending_flow_state is None:
        return False
    return (
        pending_flow_state.flow_kind in {"order", "reservation"}
        and pending_flow_state.stage == "completed"
    )


def get_latest_assistant_text(chat_turns: list[dict[str, Any]]) -> str:
    if not chat_turns:
        return ""
    latest_turn = chat_turns[-1]
    assistant_text = latest_turn.get("assistant", "")
    return assistant_text if isinstance(assistant_text, str) else ""


def get_contextual_allow_reason(
    text: str,
    run_context: RestaurantRunContext | None,
) -> str | None:
    if run_context is None or run_context.pending_flow_state is None:
        return None

    pending_flow_state = run_context.pending_flow_state
    if pending_flow_state.flow_kind is None or pending_flow_state.stage == "completed":
        return None

    if pending_flow_state.stage == "awaiting_confirmation" and _looks_like_confirmation_input(text):
        return f"{pending_flow_state.flow_kind} 확인 발화"

    if (
        pending_flow_state.flow_kind == "order"
        and pending_flow_state.stage == "awaiting_payment_method"
        and _looks_like_payment_method_input(text)
    ):
        return "결제 수단 선택 발화"

    if (
        pending_flow_state.flow_kind == "order"
        and pending_flow_state.stage == "awaiting_payment_confirmation"
        and (_looks_like_payment_confirmation_input(text) or _looks_like_confirmation_input(text))
    ):
        return "결제 확인 발화"

    if pending_flow_state.flow_kind == "order" and _looks_like_order_follow_up(text):
        return "주문 후속 발화"

    if pending_flow_state.flow_kind == "reservation" and _looks_like_reservation_follow_up(text):
        return "예약 후속 발화"

    if pending_flow_state.flow_kind == "complaints" and _looks_like_complaints_follow_up(text):
        return "불만 후속 발화"

    if pending_flow_state.flow_kind == "menu" and _looks_like_menu_follow_up(text):
        return "메뉴 후속 발화"

    return None
