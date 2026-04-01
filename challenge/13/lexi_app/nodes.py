from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from langgraph.types import Send

from .config import MEMORY_DB_PATH, get_llm
from .memory import load_memory_records, record_review_result, upsert_memory_record
from .schemas import (
    CandidateWords,
    NormalizedTerms,
    ReviewJudgment,
    RouteDecision,
    VocabularyEntries,
)
from .state import LearningState, MemoryRecord, ReviewState, TermEvidence
from .tools import locate_source_sentences, select_review_candidates


REVIEW_KEYWORDS = {
    "review",
    "quiz",
    "review words",
    "review vocabulary",
    "복습",
    "퀴즈",
    "다시 보기",
    "단어 복습",
}
ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
HANGUL_RE = re.compile(r"[가-힣]")


@lru_cache(maxsize=1)
def get_route_llm():
    return get_llm().with_structured_output(RouteDecision)


@lru_cache(maxsize=1)
def get_candidate_llm():
    return get_llm().with_structured_output(CandidateWords)


@lru_cache(maxsize=1)
def get_term_normalizer_llm():
    return get_llm().with_structured_output(NormalizedTerms)


@lru_cache(maxsize=1)
def get_entry_llm():
    return get_llm().with_structured_output(VocabularyEntries)


@lru_cache(maxsize=1)
def get_review_judge_llm():
    return get_llm().with_structured_output(ReviewJudgment)


def contains_hangul(text: str) -> bool:
    return bool(HANGUL_RE.search(text))


def english_tokens(text: str) -> list[str]:
    return ENGLISH_TOKEN_RE.findall(text)


def is_explicit_review_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if normalized in REVIEW_KEYWORDS:
        return True
    return any(keyword in normalized for keyword in REVIEW_KEYWORDS)


def looks_like_single_term(text: str) -> bool:
    normalized = text.strip()
    if not normalized or contains_hangul(normalized):
        return False
    tokens = english_tokens(normalized)
    if not tokens or len(tokens) > 5:
        return False
    allowed = re.sub(r"[A-Za-z0-9_\-\s/().]", "", normalized)
    return not allowed and len(normalized) <= 80


def looks_like_english_paragraph(text: str) -> bool:
    normalized = text.strip()
    tokens = english_tokens(normalized)
    if len(tokens) < 6:
        return False
    if contains_hangul(normalized):
        return False
    sentence_markers = sum(normalized.count(mark) for mark in ".,;:!?")
    return sentence_markers > 0 or len(normalized.split()) >= 10


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def normalize_korean_meaning(text: str) -> str:
    lowered = text.strip().lower()
    return re.sub(r"[^가-힣a-z0-9]", "", lowered)


def analyze_request(state: LearningState) -> dict:
    text = state["input_text"].strip()

    if state.get("review_state") and text and not is_explicit_review_request(text):
        return {"route": "review", "error_message": None, "assistant_message": None}

    if not text:
        message = "입력이 비어 있습니다. 영어 기술 문장, 영어 용어, 또는 복습 요청을 입력해 주세요."
        return {
            "route": "reentry",
            "assistant_message": message,
            "error_message": message,
        }

    if len(text) > 2000:
        message = "입력이 2000자를 초과했습니다. 더 짧은 영어 기술 문장 또는 용어로 다시 입력해 주세요."
        return {
            "route": "reentry",
            "assistant_message": message,
            "error_message": message,
        }

    if is_explicit_review_request(text):
        return {"route": "review", "assistant_message": None, "error_message": None}

    if contains_hangul(text):
        message = "LeXi는 영어 기술 문서 학습과 복습 요청만 처리합니다. 영어 기술 문장, 영어 용어, 또는 복습 요청을 입력해 주세요."
        return {"route": "invalid", "assistant_message": message, "error_message": message}

    if looks_like_single_term(text):
        return {"route": "single_term", "assistant_message": None, "error_message": None}

    if looks_like_english_paragraph(text):
        return {"route": "paragraph", "assistant_message": None, "error_message": None}

    if not english_tokens(text):
        message = "LeXi는 영어 기술 문서 학습과 복습 요청만 처리합니다. 영어 기술 문장, 영어 용어, 또는 복습 요청을 입력해 주세요."
        return {"route": "invalid", "assistant_message": message, "error_message": message}

    prompt = f"""
You are classifying an English technical vocabulary study request.
Choose one route from: paragraph, single_term, review, reentry, invalid.
Return only the structured output.

Input:
{text}
""".strip()
    result = get_route_llm().invoke(prompt)
    route = result.route
    if route == "reentry":
        message = "입력을 다시 확인해 주세요. 영어 기술 문장, 영어 용어, 또는 복습 요청을 입력해 주세요."
        return {"route": route, "assistant_message": message, "error_message": message}
    if route == "invalid":
        message = "LeXi는 영어 기술 문서 학습과 복습 요청만 처리합니다. 영어 기술 문장, 영어 용어, 또는 복습 요청을 입력해 주세요."
        return {"route": route, "assistant_message": message, "error_message": message}
    return {"route": route, "assistant_message": None, "error_message": None}


def extract_candidates(state: LearningState) -> dict:
    text = state["input_text"].strip()
    if state.get("route") != "paragraph" or not text:
        return {"candidate_words": [], "terms_to_study": []}

    prompt = f"""
You are helping a Korean developer study English technical writing.
Read the text and choose up to 5 English words or short terms that are worth learning.
Pick items that are important for understanding the technical meaning, not just rare words.
Return only the structured output.

Text:
{text}
""".strip()
    result = get_candidate_llm().invoke(prompt)
    candidate_words = dedupe_preserve_order(result.candidate_words)[:5]
    return {
        "candidate_words": candidate_words,
        "terms_to_study": candidate_words,
        "error_message": None,
    }


def normalize_term_request(state: LearningState) -> dict:
    text = state["input_text"].strip()
    if state.get("route") != "single_term" or not text:
        return {"terms_to_study": []}

    prompt = f"""
You are preparing study targets for a Korean developer reading English technical documents.
Normalize the input into up to 5 English technical terms to study.
Keep the terms concise and preserve the original technical meaning.
Return only the structured output.

Input:
{text}
""".strip()
    result = get_term_normalizer_llm().invoke(prompt)
    terms_to_study = dedupe_preserve_order(result.terms_to_study)[:5]
    return {
        "candidate_words": terms_to_study,
        "terms_to_study": terms_to_study,
        "error_message": None,
    }


def enrich_term(state: LearningState) -> dict:
    text = state["input_text"].strip()
    terms_to_study = state.get("terms_to_study", [])
    if not text or not terms_to_study:
        return {"term_evidence": {}}

    term_evidence: dict[str, TermEvidence] = {}
    for term in terms_to_study:
        source_sentences = locate_source_sentences.invoke({"term": term, "input_text": text})
        term_evidence[term] = {
            "term": term,
            "source_sentences": source_sentences,
        }
    return {"term_evidence": term_evidence, "error_message": None}


def build_vocabulary_entries(state: LearningState) -> dict:
    text = state["input_text"].strip()
    terms_to_study = state.get("terms_to_study", [])
    term_evidence = state.get("term_evidence", {})
    if not text or not terms_to_study:
        return {"vocabulary_entries": []}

    evidence_blocks: list[str] = []
    for term in terms_to_study:
        evidence = term_evidence.get(term, {"term": term, "source_sentences": []})
        source_sentences = evidence.get("source_sentences", []) or ["(no exact source sentence found)"]
        evidence_blocks.append(
            f"Term: {term}\nSource sentences:\n- " + "\n- ".join(source_sentences)
        )

    prompt = f"""
You are building study cards for a Korean developer reading English technical documents.
Use the original text and the term evidence below.
For each study term, return:
- word as it appears in the text or the best matching surface form
- lemma
- Korean meaning in this technical context
- source sentence from the original text
- a short Korean context note
- a short Korean explanation of why the term matters
- study priority as high, medium, or low
Return only the structured output.

Original text:
{text}

Term evidence:
{chr(10).join(evidence_blocks)}
""".strip()
    result = get_entry_llm().invoke(prompt)
    vocabulary_entries = [entry.model_dump() for entry in result.vocabulary_entries]
    return {"vocabulary_entries": vocabulary_entries, "error_message": None}


def save_memory(state: LearningState, db_path: Path = MEMORY_DB_PATH) -> dict:
    vocabulary_entries = state.get("vocabulary_entries", [])
    if not vocabulary_entries:
        return {"memory_records": load_memory_records(db_path)}

    for entry in vocabulary_entries:
        upsert_memory_record(entry, db_path=db_path)
    return {"memory_records": load_memory_records(db_path), "error_message": None}


def load_review_memory(state: LearningState, db_path: Path = MEMORY_DB_PATH) -> dict:
    memory_records = load_memory_records(db_path)
    if not memory_records:
        return {
            "memory_records": [],
            "review_queue": [],
            "error_message": "아직 복습할 단어가 없습니다. 먼저 영어 기술 문장을 학습해 단어장을 만들어 주세요.",
        }

    review_queue = select_review_candidates.invoke(
        {
            "memory_records": memory_records,
            "limit": state.get("session_review_limit", 3),
            "exclude_words": [item["word"] for item in state.get("review_history", [])],
        }
    )
    return {
        "memory_records": memory_records,
        "review_queue": review_queue,
        "error_message": None,
    }


def present_review_question(state: LearningState) -> dict:
    existing_review_state = state.get("review_state")
    text = state.get("input_text", "").strip()

    if existing_review_state and existing_review_state.get("current_word"):
        if text and not is_explicit_review_request(text):
            return {
                "review_state": {**existing_review_state, "user_answer": text},
                "assistant_message": None,
                "error_message": None,
            }
        return {"review_state": existing_review_state, "assistant_message": None, "error_message": None}

    review_queue = state.get("review_queue", [])
    memory_records = state.get("memory_records", [])
    if not review_queue:
        message = "현재 review queue가 비어 있습니다."
        return {
            "review_state": None,
            "assistant_message": message,
            "error_message": message,
        }

    current_word = review_queue[0]
    current_record = next((record for record in memory_records if record["word"] == current_word), None)
    if not current_record:
        message = f"'{current_word}' 단어의 memory record를 찾지 못했습니다."
        return {
            "review_state": None,
            "assistant_message": message,
            "error_message": message,
        }

    review_state: ReviewState = {
        "current_word": current_record["word"],
        "current_source_sentence": current_record["source_sentence"],
        "expected_meaning": current_record["meaning_in_context"],
        "user_answer": "",
        "judgment": "unknown",
        "explanation": "",
    }
    message = (
        f"단어: {review_state['current_word']}\n"
        f"문장: {review_state['current_source_sentence']}\n"
        "이 단어의 한국어 뜻을 입력해 주세요."
    )
    return {
        "review_state": review_state,
        "assistant_message": message,
        "error_message": None,
    }


def judge_review_answer(state: LearningState) -> dict:
    review_state = state.get("review_state")
    if not review_state:
        return {"error_message": "판정할 review 상태가 없습니다."}

    expected_meaning = review_state["expected_meaning"].strip()
    user_answer = review_state["user_answer"].strip()
    normalized_expected = normalize_korean_meaning(expected_meaning)
    normalized_answer = normalize_korean_meaning(user_answer)

    if not normalized_answer:
        updated_state = {
            **review_state,
            "judgment": "wrong",
            "explanation": f"정답은 '{expected_meaning}'입니다. 답안을 입력하지 않아 오답으로 처리했습니다.",
        }
        return {"review_state": updated_state, "review_judge_method": "rule", "error_message": None}

    if normalized_answer == normalized_expected or (
        normalized_answer and (normalized_answer in normalized_expected or normalized_expected in normalized_answer)
    ):
        updated_state = {
            **review_state,
            "judgment": "correct",
            "explanation": "정답입니다. 현재 문맥에서의 의미를 정확히 이해했습니다.",
        }
        return {"review_state": updated_state, "review_judge_method": "rule", "error_message": None}

    prompt = f"""
You are judging whether a Korean learner's answer matches the intended meaning of an English technical term.
Return only the structured output.
If the learner is wrong, explain briefly in Korean and include the correct Korean meaning.

English term: {review_state['current_word']}
Source sentence: {review_state['current_source_sentence']}
Expected Korean meaning: {expected_meaning}
User answer: {user_answer}
""".strip()
    llm_result = get_review_judge_llm().invoke(prompt)
    explanation = llm_result.explanation
    if llm_result.judgment == "wrong" and expected_meaning not in explanation:
        explanation = f"정답은 '{expected_meaning}'입니다. {explanation}"

    updated_state = {
        **review_state,
        "judgment": llm_result.judgment,
        "explanation": explanation,
    }
    return {"review_state": updated_state, "review_judge_method": "llm", "error_message": None}


def update_review_memory(state: LearningState, db_path: Path = MEMORY_DB_PATH) -> dict:
    review_state = state.get("review_state")
    if not review_state:
        return {"error_message": "업데이트할 review 상태가 없습니다."}

    current_word = review_state["current_word"]
    judgment = review_state["judgment"]
    record_review_result(current_word, judgment, db_path=db_path)

    remaining_queue = state.get("review_queue", [])[1:]
    review_history = state.get("review_history", []) + [
        {
            "word": current_word,
            "judgment": judgment,
            "user_answer": review_state["user_answer"],
            "expected_meaning": review_state["expected_meaning"],
            "source_sentence": review_state["current_source_sentence"],
            "explanation": review_state["explanation"],
        }
    ]
    return {
        "memory_records": load_memory_records(db_path),
        "review_queue": remaining_queue,
        "review_history": review_history,
        "assistant_message": review_state["explanation"],
        "error_message": None,
    }


def next_review_or_finish(state: LearningState) -> dict:
    review_state = state.get("review_state")
    review_history = state.get("review_history", [])
    review_queue = state.get("review_queue", [])
    session_limit = state.get("session_review_limit", 3)

    if not review_state:
        return {"error_message": "다음 review 단계를 결정할 review 상태가 없습니다."}

    judgment = review_state["judgment"]
    completed_count = len(review_history)
    reached_limit = completed_count >= session_limit

    if reached_limit:
        return {
            "assistant_message": "기본 3개 단어 복습을 마쳤어요.",
            "review_state": None,
            "continue_review": False,
            "error_message": None,
        }

    if review_queue:
        return {
            "assistant_message": "다음 문제를 보려면 `review`를 다시 입력해 주세요.",
            "review_state": None,
            "continue_review": None,
            "error_message": None,
        }

    return {
        "assistant_message": "지금 복습할 단어를 모두 확인했어요.",
        "review_state": None,
        "continue_review": False,
        "error_message": None,
    }


class EnrichmentWorkerState(dict):
    input_text: str
    term: str


def enrich_term_worker(state: EnrichmentWorkerState) -> dict:
    term = state["term"]
    source_sentences = locate_source_sentences.invoke(
        {"term": term, "input_text": state["input_text"]}
    )
    return {
        "term_evidence": {
            term: {
                "term": term,
                "source_sentences": source_sentences,
            }
        }
    }


def dispatch_term_enrichment(state: LearningState) -> list[Send]:
    return [
        Send(
            "enrich_term_worker",
            {
                "input_text": state["input_text"],
                "term": term,
            },
        )
        for term in state.get("terms_to_study", [])
    ]


def ask_for_reentry(state: LearningState) -> dict:
    message = state.get("error_message") or "입력을 다시 확인해 주세요."
    return {"assistant_message": message, "error_message": message}


def reject_out_of_scope(state: LearningState) -> dict:
    message = state.get("error_message") or "LeXi는 영어 기술 문서 학습과 복습 요청만 처리합니다."
    return {"assistant_message": message, "error_message": message}


def route_from_request(state: LearningState) -> str:
    return state.get("route") or "invalid"


def route_after_review_question(state: LearningState) -> str:
    review_state = state.get("review_state")
    if not review_state:
        return "end"
    if review_state.get("user_answer"):
        return "judge"
    return "end"


def route_after_next_review(state: LearningState) -> str:
    return "end"
