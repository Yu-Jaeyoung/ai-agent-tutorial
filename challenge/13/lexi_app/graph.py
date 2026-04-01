from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .nodes import (
    analyze_request,
    ask_for_reentry,
    build_vocabulary_entries,
    dispatch_term_enrichment,
    enrich_term_worker,
    extract_candidates,
    judge_review_answer,
    load_review_memory,
    next_review_or_finish,
    normalize_term_request,
    present_review_question,
    reject_out_of_scope,
    route_after_next_review,
    route_after_review_question,
    route_from_request,
    save_memory,
    update_review_memory,
)
from .state import LearningState


@lru_cache(maxsize=1)
def build_graph():
    graph_builder = StateGraph(LearningState)
    graph_builder.add_node("analyze_request", analyze_request)
    graph_builder.add_node(
        "extract_candidates",
        extract_candidates,
        destinations=("enrich_term_worker",),
    )
    graph_builder.add_node(
        "normalize_term_request",
        normalize_term_request,
        destinations=("enrich_term_worker",),
    )
    graph_builder.add_node(
        "enrich_term_worker",
        enrich_term_worker,
        destinations=("build_vocabulary_entries",),
    )
    graph_builder.add_node(
        "build_vocabulary_entries",
        build_vocabulary_entries,
        destinations=("save_memory",),
    )
    graph_builder.add_node("save_memory", save_memory)
    graph_builder.add_node("load_review_memory", load_review_memory)
    graph_builder.add_node("present_review_question", present_review_question)
    graph_builder.add_node("judge_review_answer", judge_review_answer)
    graph_builder.add_node("update_review_memory", update_review_memory)
    graph_builder.add_node("next_review_or_finish", next_review_or_finish)
    graph_builder.add_node("ask_for_reentry", ask_for_reentry)
    graph_builder.add_node("reject_out_of_scope", reject_out_of_scope)

    graph_builder.add_edge(START, "analyze_request")
    graph_builder.add_conditional_edges(
        "analyze_request",
        route_from_request,
        {
            "paragraph": "extract_candidates",
            "single_term": "normalize_term_request",
            "review": "load_review_memory",
            "reentry": "ask_for_reentry",
            "invalid": "reject_out_of_scope",
        },
    )
    graph_builder.add_conditional_edges("extract_candidates", dispatch_term_enrichment)
    graph_builder.add_conditional_edges("normalize_term_request", dispatch_term_enrichment)
    graph_builder.add_edge("enrich_term_worker", "build_vocabulary_entries")
    graph_builder.add_edge("build_vocabulary_entries", "save_memory")
    graph_builder.add_edge("save_memory", END)
    graph_builder.add_edge("load_review_memory", "present_review_question")
    graph_builder.add_conditional_edges(
        "present_review_question",
        route_after_review_question,
        {
            "judge": "judge_review_answer",
            "end": END,
        },
    )
    graph_builder.add_edge("judge_review_answer", "update_review_memory")
    graph_builder.add_edge("update_review_memory", "next_review_or_finish")
    graph_builder.add_conditional_edges(
        "next_review_or_finish",
        route_after_next_review,
        {
            "present": "present_review_question",
            "end": END,
        },
    )
    graph_builder.add_edge("ask_for_reentry", END)
    graph_builder.add_edge("reject_out_of_scope", END)
    return graph_builder.compile()
