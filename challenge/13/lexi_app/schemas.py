from __future__ import annotations

from pydantic import BaseModel, Field

from .state import ReviewResult, RouteName, StudyPriority


class RouteDecision(BaseModel):
    route: RouteName = Field(description="Detected learning route for the current input")
    reason: str = Field(description="Short explanation for why the route was chosen")


class CandidateWords(BaseModel):
    candidate_words: list[str] = Field(
        description="Important English technical words or short terms worth studying. Maximum 5 items."
    )


class NormalizedTerms(BaseModel):
    terms_to_study: list[str] = Field(
        description="Normalized English terms to study. Maximum 5 items."
    )


class VocabularyEntryModel(BaseModel):
    word: str = Field(description="Word or phrase as it appears in the text")
    lemma: str = Field(description="Normalized lemma")
    meaning_in_context: str = Field(description="Korean meaning in the current technical context")
    source_sentence: str = Field(description="Source sentence from the original English text")
    context_note: str = Field(description="Short Korean explanation of why this meaning fits the context")
    why_it_matters: str = Field(description="Short Korean explanation of why the term matters for technical reading")
    study_priority: StudyPriority = Field(description="Study priority level for the learner")


class VocabularyEntries(BaseModel):
    vocabulary_entries: list[VocabularyEntryModel]


class ReviewJudgment(BaseModel):
    judgment: ReviewResult = Field(description="Whether the user's Korean answer is correct, wrong, or unknown")
    explanation: str = Field(description="Short Korean explanation used when the user needs feedback")
