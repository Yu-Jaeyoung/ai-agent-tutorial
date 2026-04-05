from __future__ import annotations

import re
from datetime import datetime

from langchain_core.tools import tool

from .state import MemoryRecord


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if not SENTENCE_SPLIT_RE.search(normalized):
        return [normalized]
    return [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(normalized) if sentence.strip()]


@tool
def locate_source_sentences(term: str, input_text: str) -> list[str]:
    """Find source sentences from the original input that contain the given English term."""
    normalized_term = term.strip().lower()
    if not normalized_term:
        return []

    matched_sentences: list[str] = []
    for sentence in split_sentences(input_text):
        if normalized_term in sentence.lower():
            matched_sentences.append(sentence)
    return matched_sentences


def parse_reviewed_at(value: str | None) -> float:
    if not value:
        return float("-inf")
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return float("-inf")


@tool
def select_review_candidates(
    memory_records: list[MemoryRecord],
    limit: int = 3,
    exclude_words: list[str] | None = None,
) -> list[str]:
    """Select balanced review candidates using review count, recency, and previous mistakes."""
    excluded = {word.lower() for word in (exclude_words or [])}
    eligible_records = [
        record for record in memory_records if record["word"].lower() not in excluded
    ]

    def sort_key(record: MemoryRecord) -> tuple[int, int, float, str]:
        wrong_priority = 0 if record.get("last_review_result") == "wrong" else 1
        return (
            record.get("review_count", 0),
            wrong_priority,
            parse_reviewed_at(record.get("last_reviewed_at")),
            record["word"].lower(),
        )

    ordered_records = sorted(eligible_records, key=sort_key)
    return [record["word"] for record in ordered_records[:limit]]
