from __future__ import annotations

from datetime import timezone
from typing import Annotated, Literal

from typing_extensions import NotRequired, TypedDict


RouteName = Literal["paragraph", "single_term", "existing_term", "review", "reentry", "invalid"]
ReviewResult = Literal["correct", "wrong", "unknown"]
StudyPriority = Literal["high", "medium", "low"]

UTC = timezone.utc


def merge_term_evidence(left: dict[str, "TermEvidence"], right: dict[str, "TermEvidence"]) -> dict[str, "TermEvidence"]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class VocabularyEntry(TypedDict):
    word: str
    lemma: str
    meaning_in_context: str
    source_sentence: str
    context_note: str
    why_it_matters: str
    study_priority: StudyPriority
    previous_context: NotRequired[str]


class MemoryRecord(TypedDict):
    word: str
    lemma: str
    meaning_in_context: str
    source_sentence: str
    context_note: str
    why_it_matters: str
    study_priority: str
    created_at: str
    review_count: int
    last_reviewed_at: str | None
    last_review_result: ReviewResult | None


class TermEvidence(TypedDict):
    term: str
    source_sentences: list[str]


class ReviewState(TypedDict):
    current_word: str
    current_source_sentence: str
    expected_meaning: str
    user_answer: str
    judgment: ReviewResult
    explanation: str


class LearningState(TypedDict):
    user_id: str
    input_text: str
    route: RouteName | None
    candidate_words: list[str]
    terms_to_study: list[str]
    term_evidence: Annotated[dict[str, TermEvidence], merge_term_evidence]
    vocabulary_entries: list[VocabularyEntry]
    memory_records: list[MemoryRecord]
    review_queue: list[str]
    review_state: ReviewState | None
    review_history: list[dict[str, str]]
    continue_review: bool | None
    review_judge_method: str | None
    assistant_message: str | None
    error_message: str | None
    session_review_limit: int


def make_initial_state(input_text: str = "", user_id: str = "default") -> LearningState:
    return {
        "user_id": user_id,
        "input_text": input_text,
        "route": None,
        "candidate_words": [],
        "terms_to_study": [],
        "term_evidence": {},
        "vocabulary_entries": [],
        "memory_records": [],
        "review_queue": [],
        "review_state": None,
        "review_history": [],
        "continue_review": None,
        "review_judge_method": None,
        "assistant_message": None,
        "error_message": None,
        "session_review_limit": 3,
    }
