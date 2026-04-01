from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .graph import build_graph as compile_graph
from .nodes import is_explicit_review_request
from .state import LearningState, ReviewState, VocabularyEntry, make_initial_state


class AssistantTurnPayload(BaseModel):
    mode: Literal["learning", "review_question", "review_feedback", "error"]
    assistant_text: str
    route: str | None
    vocabulary_entries: list[VocabularyEntry]
    review_state: ReviewState | None
    latest_review_item: dict[str, str] | None
    memory_count: int
    review_queue_length: int
    review_judge_method: str | None


def build_graph():
    return compile_graph()


def prepare_turn_state(previous_state: LearningState | None, user_text: str) -> LearningState:
    next_state = make_initial_state(user_text)
    if not previous_state:
        return next_state

    next_state["session_review_limit"] = previous_state.get("session_review_limit", 3)
    next_state["memory_records"] = previous_state.get("memory_records", [])

    has_active_review = bool(previous_state.get("review_state"))
    explicit_review_request = is_explicit_review_request(user_text)

    if has_active_review and not explicit_review_request:
        next_state["review_state"] = previous_state["review_state"]
        next_state["review_queue"] = previous_state.get("review_queue", [])
        next_state["review_history"] = previous_state.get("review_history", [])
        return next_state

    if explicit_review_request:
        next_state["review_history"] = []
        return next_state

    next_state["review_history"] = previous_state.get("review_history", [])
    return next_state


def run_turn(previous_state: LearningState | None, user_text: str) -> LearningState:
    graph = build_graph()
    prepared_state = prepare_turn_state(previous_state, user_text)
    return graph.invoke(prepared_state)


def summarize_turn_result(state: LearningState) -> AssistantTurnPayload:
    assistant_text = state.get("assistant_message") or ""
    route = state.get("route")
    vocabulary_entries = state.get("vocabulary_entries", [])
    review_state = state.get("review_state")
    review_judge_method = state.get("review_judge_method")
    review_history = state.get("review_history", [])
    latest_review_item = review_history[-1] if review_history else None

    if state.get("error_message"):
        mode: Literal["learning", "review_question", "review_feedback", "error"] = "error"
    elif review_judge_method:
        mode = "review_feedback"
    elif route == "review" and review_state and not review_state.get("user_answer"):
        mode = "review_question"
    else:
        mode = "learning"

    return AssistantTurnPayload(
        mode=mode,
        assistant_text=assistant_text,
        route=route,
        vocabulary_entries=vocabulary_entries,
        review_state=review_state,
        latest_review_item=latest_review_item,
        memory_count=len(state.get("memory_records", [])),
        review_queue_length=len(state.get("review_queue", [])),
        review_judge_method=review_judge_method,
    )
