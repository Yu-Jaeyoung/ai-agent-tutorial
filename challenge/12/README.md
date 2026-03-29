# Challenge 12

## LeXi v2

`LeXi`는 `Lexicon`에서 이름을 가져온 영어 기술 문서 학습 에이전트다.  
이번 단계에서는 기존의 단순 단어 추출 MVP를 업그레이드해, 입력 유형을 판단하고, 조건 분기하며, 도구를 사용해 근거를 보강하는 `Gemini + LangGraph` 기반 학습 에이전트로 확장한다.

핵심 목표는 단순히 단어를 뽑는 것이 아니라, 사용자의 입력 의도에 따라 다른 학습 흐름으로 라우팅하고, 각 단어를 더 신뢰할 수 있는 근거와 함께 정리하는 것이다.

실제 구현은 [`main.ipynb`](/Users/jaeyoung/Developments/study/agents/ai-agent-tutorial/challenge/12/main.ipynb)에 담고, 이 문서는 그 설계 의도를 정리한다.

## Step 1. Agent Design

### Theme

- `Education & Learning`

### Agent Name

- `LeXi v2`

### Purpose

- 영어 기술 문서를 읽을 때 학습 가치가 높은 단어를 자동으로 추린다.
- 단어 하나만 입력한 경우에도 바로 학습용 엔트리로 확장할 수 있다.
- 복습 요청이 들어오면 기존 단어장 정보를 바탕으로 복습 세트를 만든다.
- 각 단어를 문맥뿐 아니라 도구 기반 근거와 함께 정리한다.

### Problem It Solves

- 기술 문서를 읽으며 중요한 단어를 수동으로 골라야 하는 번거로움
- 같은 단어라도 문맥에 따라 뜻이 달라 사전 뜻만으로는 이해하기 어려운 문제
- 입력이 문단인지, 단어 하나인지, 복습 요청인지에 따라 다른 흐름이 필요한 문제
- 단어를 정리하더라도 왜 그 뜻인지 근거가 부족한 문제

### Key Features

- Gemini가 입력 의도를 분류해 적절한 학습 경로로 라우팅
- Gemini가 학습 가치가 높은 단어 후보를 추출
- Custom Tool이 원문에서 단어가 나온 문장을 찾아 근거를 보강
- LangGraph가 조건 분기와 병렬 처리 흐름을 관리
- 구조화된 단어장 또는 복습 결과를 상태에 저장

## Step 2. Workflow Design

### High-Level Workflow

아래 Mermaid 다이어그램에서 실선은 이번 과제에서 구현하는 흐름이고, 점선은 향후 확장 흐름이다.

```mermaid
flowchart TD
    A[User Input]
    B[Node 1: analyze_request]

    C[Node 2: extract_candidates]
    D[Node 2b: normalize_term_request]
    E[Node 3: enrich_term with tool]
    F[Node 4: build_vocabulary_entries]
    G[Node 5: build_review_set]
    H[Node X: ask_for_clarification]

    I[(Future) Study memory store]
    J[(Future) Local glossary search]
    K[(Future) Quiz and review history]
    L[(Future) Personalized study priority]

    A --> B
    B -->|paragraph| C
    B -->|single_term| D
    B -->|review| G
    B -->|unclear| H

    C --> E
    D --> E
    E --> F
    F --> I

    I -. future .-> J
    I -. future .-> K
    K -. future .-> L
```

### Routing Strategy

`analyze_request`는 입력을 다음 네 가지 중 하나로 분류한다.

- `paragraph`
  - 영어 기술 문장 또는 문단 입력
- `single_term`
  - 단어 하나 또는 짧은 기술 표현 입력
- `review`
  - 복습, 퀴즈, 다시 보기 요청
- `unclear`
  - 빈 입력 또는 학습 흐름으로 처리하기 어려운 입력

이 분류 결과를 바탕으로 LangGraph의 Conditional Edge가 서로 다른 경로로 라우팅한다.

## Step 3. Foundation Building

### Why This Structure

- 이번 과제의 핵심은 단순 선형 흐름이 아니라 `입력 분석 -> 조건 분기 -> 단어별 보강 -> 결과 생성`이다.
- 따라서 기존의 2-node 선형 그래프보다, 역할이 분리된 다중 노드 구조가 더 적합하다.
- 상태는 여전히 `MessagesState` 대신 작은 `custom state`를 사용한다.
- 각 함수는 복잡한 규칙 계산보다 `프롬프트 준비 -> Gemini 호출 또는 Tool 호출 -> 상태 업데이트`에 집중한다.

### State Design

```python
class VocabularyEntry(TypedDict):
    word: str
    lemma: str
    meaning_in_context: str
    source_sentence: str
    context_note: str
    glossary_note: str

class TermEvidence(TypedDict):
    term: str
    source_sentences: list[str]
    glossary_hits: list[str]

class ReviewCard(TypedDict):
    word: str
    question: str
    answer: str

class LearningState(TypedDict):
    input_text: str
    route: str
    candidate_words: list[str]
    terms_to_study: list[str]
    term_evidence: dict[str, TermEvidence]
    vocabulary_entries: list[VocabularyEntry]
    review_cards: list[ReviewCard]
```

각 필드는 다음 의미를 가진다.

- `input_text`: 사용자가 입력한 원문
- `route`: 입력 분류 결과
- `candidate_words`: 문단에서 뽑은 후보 단어
- `terms_to_study`: 최종 학습 대상으로 확정된 단어 목록
- `term_evidence`: tool 기반 보강 정보
- `vocabulary_entries`: 최종 단어장 엔트리
- `review_cards`: 복습 또는 퀴즈용 카드

## Step 4. Node Design

### 1. `analyze_request`

- 입력 텍스트를 읽는다.
- Gemini에게 입력 유형을 분류하게 한다.
- 결과를 `route`에 저장한다.

### 2. `extract_candidates`

- `route == "paragraph"`일 때 실행한다.
- Gemini에게 학습 가치가 높은 단어를 최대 5개 고르게 한다.
- 결과를 `candidate_words`와 `terms_to_study`에 저장한다.

### 3. `normalize_term_request`

- `route == "single_term"`일 때 실행한다.
- 짧은 단어 또는 표현 입력을 학습 대상으로 정규화한다.
- 결과를 `terms_to_study`에 저장한다.

### 4. `enrich_term`

- `terms_to_study`의 각 단어를 개별적으로 처리한다.
- Custom Tool을 사용해 원문에서 관련 문장을 찾는다.
- 결과를 `term_evidence`에 누적한다.
- 이 단계는 병렬 처리 대상으로 설계한다.

### 5. `build_vocabulary_entries`

- `terms_to_study`와 `term_evidence`를 읽는다.
- Gemini에게 각 단어의 문맥 기반 뜻과 설명을 구조화하게 한다.
- 결과를 `vocabulary_entries`에 저장한다.

### 6. `build_review_set`

- `route == "review"`일 때 실행한다.
- 기존 단어장 데이터를 바탕으로 복습 카드나 간단한 질문 세트를 만든다.
- 결과를 `review_cards`에 저장한다.

### 7. `ask_for_clarification`

- `route == "unclear"`일 때 실행한다.
- 더 명확한 입력을 요청하는 안내 문구를 반환한다.

## Step 5. Conditional Edge

이번 과제에서 반드시 하나 이상의 Conditional Edge를 구현한다.

기본 연결은 아래처럼 유지한다.

```text
START -> analyze_request

analyze_request
  - paragraph -> extract_candidates -> enrich_term -> build_vocabulary_entries -> END
  - single_term -> normalize_term_request -> enrich_term -> build_vocabulary_entries -> END
  - review -> build_review_set -> END
  - unclear -> ask_for_clarification -> END
```

## Step 6. Tool Integration

### Mandatory Tool

이번 구현에서는 최소 1개의 Tool을 반드시 통합한다.

추천 기본 도구는 아래와 같다.

#### `locate_source_sentences`

- 입력:
  - `term`
  - `input_text`
- 역할:
  - 입력 텍스트 안에서 해당 단어 또는 표현이 포함된 문장을 찾는다.
- 출력:
  - 관련 원문 문장 리스트
- 장점:
  - 문맥 기반 학습이라는 LeXi의 목적과 가장 직접적으로 연결된다.
  - 모델만으로 처리하는 것보다 근거가 명확하다.

### Optional Future Tools

- `search_local_glossary`
  - 로컬 기술 용어집 검색
- `web_search_tech_definition`
  - 외부 기술 용어 정의 검색

이번 단계에서는 Custom Tool 하나를 우선 구현하고, 추가 tool은 확장 범위로 둔다.

## Step 7. Parallel Execution

Optional requirement를 반영하기 위해 `enrich_term` 단계는 병렬 처리 가능하도록 설계한다.

- `terms_to_study`의 각 단어에 대해 `Send API`로 병렬 worker를 실행
- 각 worker는 하나의 term만 담당
- 각 결과를 `term_evidence`에 병합
- 이후 `build_vocabulary_entries`가 병합된 결과를 읽어 최종 엔트리를 만든다

이 구조는 단어 수가 많아질수록 체감 성능 개선에 유리하다.

## Step 8. Memory Design

이번 단계에서는 Memory를 선택 기능으로 둔다.

### Optional Memory Scope

- 학습한 단어 기록
- 마지막으로 생성한 뜻과 출처 문장 저장
- review 모드에서 이전 단어장 재활용

초기 버전에서는 간단한 로컬 JSON 또는 LangGraph checkpointer 수준의 메모리만 고려한다.  
개인화 우선순위 추천이나 장기 학습 기록 분석은 향후 확장 범위다.

## Implementation Scope

### 이번 단계에서 구현하는 것

- `Gemini + LangGraph` 기반 최소 3개 이상의 node
- 최소 1개의 Conditional Edge
- 최소 1개의 Tool 통합
- `custom state` 기반 다중 노드 파이프라인
- notebook 안에서 설계 문서와 구현을 함께 제시
- 필요 시 `Send API` 기반 병렬 처리까지 확장

### 이번 단계에서 구현하지 않는 것

- 완전한 장기 메모리 시스템
- 로컬 glossary 데이터베이스 구축
- 웹 UI
- 고급 학습 통계
- 난이도 기반 개인화 추천
- 장기 복습 스케줄링

## Notebook Plan

구현 노트북은 [`main.ipynb`](/Users/jaeyoung/Developments/study/agents/ai-agent-tutorial/challenge/12/main.ipynb)에 작성하며, 셀 구성은 아래 순서를 따른다.

1. LeXi v2 소개와 Mermaid workflow
2. `load_dotenv`, `init_chat_model`, LangGraph import
3. 상태 타입과 structured output 타입 정의
4. `analyze_request` 구현
5. `extract_candidates` 구현
6. `normalize_term_request` 구현
7. Custom Tool 구현
8. `enrich_term` 구현
9. `build_vocabulary_entries` 구현
10. Conditional Edge 연결
11. 필요 시 `Send API` 병렬 처리 연결
12. 샘플 입력 실행
13. 결과 확인 및 향후 확장 정리

## Dependencies And Run Notes

- `langgraph`
- `langchain`
- `langchain-google-genai`
- `pydantic`
- `python-dotenv`

실행 전 `.env`에 `GOOGLE_API_KEY`가 있어야 한다.  
모델명은 기본적으로 `gemini-3-flash-preview`를 사용하고, 필요하면 `GOOGLE_GENAI_MODEL` 환경변수로 바꿀 수 있다.

예시:

```bash
uv sync
uv run jupyter notebook
```

## Test Plan

- `analyze_request`가 입력을 올바르게 분류하는지 확인
- `paragraph` 입력 시 `candidate_words`가 비어 있지 않은지 확인
- `single_term` 입력 시 `terms_to_study`가 1개 이상 생성되는지 확인
- Tool이 실제로 원문에서 source sentence를 찾는지 확인
- `build_vocabulary_entries` 실행 후 `vocabulary_entries`가 생성되는지 확인
- Conditional Edge가 `paragraph`, `single_term`, `review`, `unclear`를 다른 경로로 보내는지 확인
- 병렬 처리 적용 시 각 term worker 결과가 정상 병합되는지 확인
- 빈 입력일 때 clarification 경로로 가는지 확인

## Completion Criteria

이번 과제의 완료 기준은 아래와 같다.

- LangGraph를 사용한다.
- 최소 3개의 functioning node를 구현한다.
- 최소 1개의 Conditional Edge를 구현한다.
- 최소 1개의 Tool을 통합한다.
- 설계 문서와 코드를 Jupyter Notebook에 함께 포함한다.
- 입력 유형에 따라 다른 학습 경로로 분기할 수 있다.
- 구조화된 단어장 결과를 생성할 수 있다.

Memory와 Multi-Tool Integration은 선택 확장 범위로 남긴다.
