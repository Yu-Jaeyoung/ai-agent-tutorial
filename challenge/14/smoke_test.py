from __future__ import annotations

import tempfile
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from lexi_app import nodes
from lexi_app.memory import initialize_memory_db, load_memory_records, upsert_memory_record
from lexi_app.schemas import CandidateWords, NormalizedTerms, ReviewJudgment, VocabularyEntries, VocabularyEntryModel
from lexi_app.state import LearningState, VocabularyEntry, make_initial_state


class FakeCandidateLLM:
    def invoke(self, prompt: str) -> CandidateWords:
        return CandidateWords(candidate_words=["latency", "invalidation"])


class FakeTermNormalizerLLM:
    def invoke(self, prompt: str) -> NormalizedTerms:
        return NormalizedTerms(terms_to_study=["backward compatibility"])


class FakeEntryLLM:
    def invoke(self, prompt: str) -> VocabularyEntries:
        if "backward compatibility" in prompt:
            return VocabularyEntries(
                vocabulary_entries=[
                    VocabularyEntryModel(
                        word="backward compatibility",
                        lemma="backward compatibility",
                        meaning_in_context="하위 호환성",
                        source_sentence="Backward compatibility keeps older clients working.",
                        context_note="이전 버전 사용자도 계속 동작하게 하는 의미다.",
                        why_it_matters="API와 배포 전략 문서에서 자주 등장한다.",
                        study_priority="high",
                    )
                ]
            )

        return VocabularyEntries(
            vocabulary_entries=[
                VocabularyEntryModel(
                    word="latency",
                    lemma="latency",
                    meaning_in_context="지연 시간",
                    source_sentence="Caching reduces latency, but inconsistent invalidation can cause stale data.",
                    context_note="응답 속도와 성능을 설명하는 문맥이다.",
                    why_it_matters="성능과 분산 시스템 문서에서 중요한 개념이다.",
                    study_priority="high",
                ),
                VocabularyEntryModel(
                    word="invalidation",
                    lemma="invalidation",
                    meaning_in_context="무효화",
                    source_sentence="Caching reduces latency, but inconsistent invalidation can cause stale data.",
                    context_note="캐시된 데이터를 더 이상 유효하지 않게 만드는 과정이다.",
                    why_it_matters="캐시 일관성과 데이터 정확성을 이해할 때 중요하다.",
                    study_priority="medium",
                ),
            ]
        )


class FakeReviewJudgeLLM:
    def invoke(self, prompt: str) -> ReviewJudgment:
        return ReviewJudgment(
            judgment="wrong",
            explanation="정답은 '지연 시간'입니다. 응답이 늦어지는 시간을 뜻합니다.",
        )


def build_test_graph(temp_db: Path):
    def save_memory(state: LearningState) -> dict:
        return nodes.save_memory(state, db_path=temp_db)

    def load_review_memory(state: LearningState) -> dict:
        return nodes.load_review_memory(state, db_path=temp_db)

    def update_review_memory(state: LearningState) -> dict:
        return nodes.update_review_memory(state, db_path=temp_db)

    graph_builder = StateGraph(LearningState)
    graph_builder.add_node("analyze_request", nodes.analyze_request)
    graph_builder.add_node("extract_candidates", nodes.extract_candidates, destinations=("enrich_term_worker",))
    graph_builder.add_node("normalize_term_request", nodes.normalize_term_request, destinations=("enrich_term_worker",))
    graph_builder.add_node("enrich_term_worker", nodes.enrich_term_worker, destinations=("build_vocabulary_entries",))
    graph_builder.add_node("build_vocabulary_entries", nodes.build_vocabulary_entries, destinations=("save_memory",))
    graph_builder.add_node("save_memory", save_memory)
    graph_builder.add_node("load_review_memory", load_review_memory)
    graph_builder.add_node("present_review_question", nodes.present_review_question)
    graph_builder.add_node("judge_review_answer", nodes.judge_review_answer)
    graph_builder.add_node("update_review_memory", update_review_memory)
    graph_builder.add_node("next_review_or_finish", nodes.next_review_or_finish)
    graph_builder.add_node("ask_for_reentry", nodes.ask_for_reentry)
    graph_builder.add_node("reject_out_of_scope", nodes.reject_out_of_scope)

    graph_builder.add_edge(START, "analyze_request")
    graph_builder.add_conditional_edges(
        "analyze_request",
        nodes.route_from_request,
        {
            "paragraph": "extract_candidates",
            "single_term": "normalize_term_request",
            "review": "load_review_memory",
            "reentry": "ask_for_reentry",
            "invalid": "reject_out_of_scope",
        },
    )
    graph_builder.add_conditional_edges("extract_candidates", nodes.dispatch_term_enrichment)
    graph_builder.add_conditional_edges("normalize_term_request", nodes.dispatch_term_enrichment)
    graph_builder.add_edge("enrich_term_worker", "build_vocabulary_entries")
    graph_builder.add_edge("build_vocabulary_entries", "save_memory")
    graph_builder.add_edge("save_memory", END)
    graph_builder.add_edge("load_review_memory", "present_review_question")
    graph_builder.add_conditional_edges(
        "present_review_question",
        nodes.route_after_review_question,
        {
            "judge": "judge_review_answer",
            "end": END,
        },
    )
    graph_builder.add_edge("judge_review_answer", "update_review_memory")
    graph_builder.add_edge("update_review_memory", "next_review_or_finish")
    graph_builder.add_conditional_edges(
        "next_review_or_finish",
        nodes.route_after_next_review,
        {
            "present": "present_review_question",
            "end": END,
        },
    )
    graph_builder.add_edge("ask_for_reentry", END)
    graph_builder.add_edge("reject_out_of_scope", END)
    return graph_builder.compile()


def run_smoke_tests() -> None:
    candidate_llm_backup = nodes.get_candidate_llm
    term_normalizer_llm_backup = nodes.get_term_normalizer_llm
    entry_llm_backup = nodes.get_entry_llm
    review_judge_llm_backup = nodes.get_review_judge_llm

    nodes.get_candidate_llm = lambda: FakeCandidateLLM()
    nodes.get_term_normalizer_llm = lambda: FakeTermNormalizerLLM()
    nodes.get_entry_llm = lambda: FakeEntryLLM()
    nodes.get_review_judge_llm = lambda: FakeReviewJudgeLLM()

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db = Path(temp_dir) / "lexi_memory.db"
            graph = build_test_graph(temp_db)

            empty_result = graph.invoke(make_initial_state(""))
            assert empty_result["route"] == "reentry"
            assert empty_result["error_message"]

            invalid_result = graph.invoke(make_initial_state("안녕하세요"))
            assert invalid_result["route"] == "invalid"
            assert invalid_result["error_message"]

            paragraph_result = graph.invoke(
                make_initial_state(
                    "Caching reduces latency, but inconsistent invalidation can cause stale data."
                )
            )
            assert paragraph_result["route"] == "paragraph"
            assert len(paragraph_result["vocabulary_entries"]) >= 1
            assert len(paragraph_result["memory_records"]) >= 1

            single_term_result = graph.invoke(make_initial_state("backward compatibility"))
            assert single_term_result["route"] == "single_term"
            assert single_term_result["vocabulary_entries"][0]["word"] == "backward compatibility"

            review_prompt = graph.invoke(make_initial_state("review"))
            assert review_prompt["route"] == "review"
            assert review_prompt["review_state"]
            assert "한국어 뜻" in review_prompt["assistant_message"]

            expected_meaning = review_prompt["review_state"]["expected_meaning"]
            correct_answer_state = {**review_prompt, "input_text": expected_meaning}
            correct_result = graph.invoke(correct_answer_state)
            assert correct_result["review_judge_method"] == "rule"
            correct_history = correct_result.get("review_history", [])
            assert any("정답입니다." in h.get("explanation", "") for h in correct_history)

            review_prompt_again = graph.invoke(make_initial_state("review"))
            wrong_answer_state = {**review_prompt_again, "input_text": "분산 시스템"}
            wrong_result = graph.invoke(wrong_answer_state)
            assert wrong_result["review_judge_method"] == "llm"
            wrong_history = wrong_result.get("review_history", [])
            assert any("정답은" in h.get("explanation", "") for h in wrong_history)

            # --- route_after_next_review routing tests ---
            state_with_queue = {**make_initial_state(""), "review_queue": ["word1"], "continue_review": None}
            assert nodes.route_after_next_review(state_with_queue) == "present"

            state_finished = {**make_initial_state(""), "review_queue": [], "continue_review": False}
            assert nodes.route_after_next_review(state_finished) == "end"

            state_limit_reached = {**make_initial_state(""), "review_queue": ["word1"], "continue_review": False}
            assert nodes.route_after_next_review(state_limit_reached) == "end"

            # --- DB schema round-trip test (why_it_matters, study_priority) ---
            test_entry: VocabularyEntry = {
                "word": "schema_test",
                "lemma": "schema_test",
                "meaning_in_context": "스키마 테스트",
                "source_sentence": "This is a schema test.",
                "context_note": "테스트 전용 항목이다.",
                "why_it_matters": "DB 마이그레이션 검증용이다.",
                "study_priority": "high",
            }
            upsert_memory_record(test_entry, user_id="test_user", db_path=temp_db)
            records = load_memory_records(user_id="test_user", db_path=temp_db)
            matched = [r for r in records if r["word"] == "schema_test"]
            assert len(matched) == 1
            assert matched[0]["why_it_matters"] == "DB 마이그레이션 검증용이다."
            assert matched[0]["study_priority"] == "high"

            print("Smoke tests passed:")
            print("- empty input")
            print("- invalid input")
            print("- paragraph learning")
            print("- single-term learning")
            print("- review start")
            print("- review correct answer")
            print("- review wrong answer")
            print("- route_after_next_review routing")
            print("- DB schema round-trip (why_it_matters, study_priority)")
    finally:
        nodes.get_candidate_llm = candidate_llm_backup
        nodes.get_term_normalizer_llm = term_normalizer_llm_backup
        nodes.get_entry_llm = entry_llm_backup
        nodes.get_review_judge_llm = review_judge_llm_backup


if __name__ == "__main__":
    run_smoke_tests()
