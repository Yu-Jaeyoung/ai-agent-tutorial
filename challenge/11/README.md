# Challenge 11

## LeXi

`LeXi`는 `Lexicon`에서 이름을 가져온 영어 기술 문서 학습 에이전트다.  
영어 기술 문장이나 문단을 입력받아 학습할 만한 핵심 단어를 고르고, 각 단어가 문맥 안에서 어떤 뜻으로 쓰였는지 단어장 형태로 정리한다.

이번 구현은 `Gemini + LangGraph` 기반의 최소 기능 MVP다.  
복잡한 규칙 기반 후보 추출 대신, `init_chat_model(..., model_provider="google_genai")`로 초기화한 Gemini 모델이 두 개의 LangGraph 노드에서 각각 역할을 분담한다.

실제 구현은 [`main.ipynb`](/Users/jaeyoung/Developments/study/ai-agent-tutorial/challenge/11/main.ipynb)에 담고, 이 문서는 그 설계 의도를 정리한다.

## Step 1. Agent Design

### Theme

- `Education & Learning`

### Agent Name

- `LeXi`

### Purpose

- 영어 기술 문서를 읽을 때 학습 가치가 있는 단어를 자동으로 추린다.
- 단어를 사전식 번역이 아니라 현재 문맥 안의 의미로 정리한다.
- 출처 문장까지 함께 기록해 나중에 다시 확인할 수 있는 단어장 기반을 만든다.

### Problem It Solves

- 기술 문서를 읽으며 모르는 단어를 수동으로 정리해야 하는 번거로움
- 같은 단어라도 기술 문맥에 따라 의미가 달라 사전 뜻만으로 이해하기 어려운 문제
- 나중에 단어를 다시 볼 때 어떤 문장에서 나왔는지 추적하기 어려운 문제

### Key Features

- Gemini가 영어 기술 문장에서 학습 가치가 높은 단어 후보를 추출
- Gemini가 각 단어를 문맥 기준으로 해석해 뜻과 출처 문장을 정리
- 구조화된 단어장 결과를 LangGraph 상태에 저장해 다음 단계로 넘김

### Workflow

아래 Mermaid 다이어그램에서 실선은 이번 과제에서 구현하는 흐름이고, 점선은 향후 확장 흐름이다.

```mermaid
flowchart TD
    A[User Input: English technical sentence or paragraph]
    B[Node 1: Extract learning-worthy words]
    C[Node 2: Build context-based vocabulary entries]
    D[Notebook Output: Structured vocabulary list]

    E[(Future) Vocabulary storage]
    F[(Future) Search words and trace sources]
    G[(Future) Frequency analysis and study priority]
    H[(Future) Review and quiz generation]

    A --> B --> C --> D
    C -. future .-> E
    E -. future .-> F
    E -. future .-> G
    G -. future .-> H
```

## Step 2. Foundation Building

### Why This Structure

- 이번 과제의 핵심은 대화형 메시지 관리보다 `입력 텍스트 -> 후보 단어 -> 단어장 엔트리` 흐름이다.
- 그래서 `MessagesState` 대신 작은 `custom state`를 사용한다.
- 함수는 길게 규칙을 계산하지 않고, `프롬프트 준비 -> Gemini 호출 -> 상태 업데이트`만 담당하도록 단순화한다.

### State Design

```python
class VocabularyEntry(TypedDict):
    word: str
    lemma: str
    meaning_in_context: str
    source_sentence: str
    context_note: str

class LearningState(TypedDict):
    input_text: str
    candidate_words: list[str]
    vocabulary_entries: list[VocabularyEntry]
```

각 필드는 다음 의미를 가진다.

- `word`: 원문에서의 단어 또는 표현
- `lemma`: 정규화된 표제어
- `meaning_in_context`: 현재 문맥에서의 뜻
- `source_sentence`: 단어가 나온 원문 문장
- `context_note`: 왜 이런 뜻으로 읽어야 하는지에 대한 짧은 설명

### Structured Output

노트북에서는 Gemini의 structured output을 사용해 결과 형식을 고정한다.

- 후보 단어 추출용 출력 모델 1개
- 단어장 엔트리 생성용 출력 모델 1개

이 구조를 쓰면 별도의 긴 후처리 함수 없이도 각 노드의 역할이 분명해진다.

### Nodes

#### 1. `extract_candidates`

- 입력 텍스트를 읽는다.
- Gemini에게 학습 가치가 높은 단어를 최대 5개 고르게 한다.
- 결과를 `candidate_words`에 저장한다.

#### 2. `build_vocabulary_entries`

- `candidate_words`와 원문 텍스트를 읽는다.
- Gemini에게 각 단어의 문맥 기반 뜻, 표제어, 출처 문장을 구조화해서 생성하게 한다.
- 결과를 `vocabulary_entries`에 저장한다.

### Basic Graph

이번 단계의 LangGraph 연결은 아래처럼 유지한다.

```text
START -> extract_candidates -> build_vocabulary_entries -> END
```

## Implementation Scope

### 이번 단계에서 구현하는 것

- `load_dotenv()`와 `init_chat_model(..., model_provider="google_genai")` 기반 모델 초기화
- LangGraph custom state 정의
- 최소 2개의 functioning node 구현
- Gemini structured output 기반 후보 단어 추출
- Gemini structured output 기반 단어장 엔트리 생성
- 설계 문서와 코드를 모두 포함한 Jupyter Notebook 작성

### 이번 단계에서 구현하지 않는 것

- 단어장 영속 저장
- 단어 검색 및 출처 추적 UI
- 빈도 통계
- 우선 학습 단어 추천
- 복습 및 퀴즈 생성
- 멀티턴 대화형 학습 세션 관리

저장, 검색, 통계, 퀴즈는 이번 단계에서는 설계만 하고 구현하지 않는다.

## Notebook Plan

구현 노트북은 [`main.ipynb`](/Users/jaeyoung/Developments/study/ai-agent-tutorial/challenge/11/main.ipynb)에 작성하며, 셀 구성은 아래 순서를 따른다.

1. LeXi 소개와 Mermaid workflow
2. `load_dotenv`, `init_chat_model`, LangGraph import
3. 상태 타입과 structured output 타입 정의
4. `extract_candidates` 구현
5. `build_vocabulary_entries` 구현
6. 그래프 연결 및 `compile`
7. 샘플 입력 실행
8. 결과 확인 및 향후 확장 정리

Notebook은 설계 설명과 코드가 함께 들어 있는 최종 제출 산출물로 사용한다.

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

- 노트북이 `load_dotenv()` 후 Gemini 모델을 초기화하는지 확인
- `extract_candidates` 실행 후 `candidate_words`가 비어 있지 않은지 확인
- `build_vocabulary_entries` 실행 후 `vocabulary_entries`가 1개 이상 생성되는지 확인
- 각 엔트리에 `word`, `lemma`, `meaning_in_context`, `source_sentence`, `context_note`가 포함되는지 확인
- 두 함수 본문이 짧고 역할이 분명한지 확인
- 빈 입력일 때 후보와 엔트리 모두 빈 리스트를 반환하는지 확인

## Completion Criteria

이번 과제의 완료 기준은 아래와 같다.

- LangGraph를 사용한다.
- 최소 2개의 functioning node를 구현한다.
- 설계 문서와 코드를 Jupyter Notebook에 함께 포함한다.
- Gemini가 입력 텍스트를 읽고 구조화된 단어장 결과를 생성한다.

영속 저장과 검색 기능은 차기 확장 범위로 남긴다.
