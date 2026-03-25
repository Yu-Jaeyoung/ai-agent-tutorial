    # Challenge 11

## LeXi

`LeXi`는 `Lexicon`에서 이름을 가져온 영어 기술 문서 학습 에이전트다.  
영어 기술 문장이나 문단을 입력받아 학습이 필요한 핵심 단어를 추출하고, 각 단어가 해당 문맥에서 어떤 의미로 쓰였는지 구조화된 단어장 형태로 정리하는 것을 목표로 한다.

이 문서는 과제 요구사항에 맞춘 설계 문서이며, 실제 구현은 [`main.ipynb`](/Users/jaeyoung/Developments/study/ai-agent-tutorial/challenge/11/main.ipynb)에 담는다.  
이번 단계에서는 LangGraph 기반의 최소 기능만 구현하고, 저장·검색·통계·퀴즈 기능은 향후 확장 범위로 남긴다.

## Step 1. Agent Design

### Theme

- `Education & Learning`

### Agent Name

- `LeXi`

### Purpose

- 영어 기술 문서를 읽을 때 학습 가치가 높은 단어를 자동으로 추출한다.
- 단어를 사전식 번역이 아니라 문장 안의 실제 의미를 기준으로 해석한다.
- 단어, 표제어, 출처 문장, 문맥 설명을 함께 정리해 다시 복습할 수 있는 기반을 만든다.

### Problem It Solves

- 기술 문서를 읽다가 모르는 단어를 일일이 따로 정리해야 하는 번거로움
- 같은 단어라도 기술 문맥에 따라 의미가 달라져 사전 뜻만으로는 이해가 어려운 문제
- 나중에 단어를 다시 볼 때 어떤 문장과 맥락에서 나왔는지 추적하기 어려운 문제

### Key Features

- 영어 기술 문장/문단에서 학습 필요 단어 후보 추출
- 문맥 기반 뜻 정리와 표제어 정규화
- 출처 문장과 학습 이유를 포함한 구조화된 단어장 생성

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

### Why LangGraph

- 입력 처리와 결과 생성을 노드 단위로 나눠 학습 흐름을 명확하게 표현할 수 있다.
- 이번에는 최소 2개 노드만 사용하지만, 이후 저장·검색·복습 노드를 자연스럽게 추가할 수 있다.
- 교육용 에이전트를 상태 기반 워크플로로 확장하기에 적합하다.

### State Design

이번 과제에서는 `MessagesState` 대신 `custom state`를 사용한다.  
이유는 단순 대화 메시지보다 문장 목록, 단어 후보, 구조화된 단어장 엔트리 같은 데이터를 직접 다루는 편이 더 적합하기 때문이다.

```python
class VocabularyEntry(TypedDict):
    word: str
    lemma: str
    meaning_in_context: str
    source_sentence: str
    context_note: str
    reason_to_learn: str

class LearningState(TypedDict):
    input_text: str
    sentences: list[str]
    candidate_words: list[str]
    vocabulary_entries: list[VocabularyEntry]
```

각 필드는 다음 의미를 가진다.

- `word`: 원문에 등장한 단어 형태
- `lemma`: 정규화한 표제어
- `meaning_in_context`: 현재 문맥에서의 뜻
- `source_sentence`: 단어가 등장한 원문 문장
- `context_note`: 왜 이런 의미로 해석했는지에 대한 짧은 설명
- `reason_to_learn`: 학습 가치가 있는 이유

### Nodes

#### 1. `extract_candidates`

- 입력 텍스트를 문장 단위로 정리한다.
- 기술 문맥에서 학습 가치가 높은 단어 후보를 추출한다.
- 결과를 `candidate_words`에 저장한다.

#### 2. `build_vocabulary_entries`

- 후보 단어별로 출처 문장을 찾는다.
- 문맥 기반 의미와 간단한 해설을 만든다.
- 구조화된 단어장 엔트리를 `vocabulary_entries`에 저장한다.

### Basic Graph

이번 단계의 LangGraph 연결은 아래처럼 단순하게 유지한다.

```text
START -> extract_candidates -> build_vocabulary_entries -> END
```

## Implementation Scope

### 이번 단계에서 구현하는 것

- LangGraph 기반 custom state 정의
- 최소 2개의 functioning node 구현
- 영어 기술 문장/문단 입력 예시 실행
- 구조화된 단어장 결과 출력
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

1. 과제 개요와 LeXi 소개
2. LangGraph 및 기본 의존성 import
3. `VocabularyEntry`, `LearningState` 정의
4. `extract_candidates` 노드 구현
5. `build_vocabulary_entries` 노드 구현
6. 그래프 연결 및 `compile`
7. 샘플 입력 실행
8. 결과 확인 및 향후 확장 정리

Notebook은 설계 설명과 코드가 함께 들어 있는 최종 제출 산출물로 사용한다.

## Test Plan

- 영어 기술 문장을 입력했을 때 두 노드가 순서대로 실행되는지 확인
- 결과에 1개 이상의 단어 엔트리가 생성되는지 확인
- 각 엔트리에 `word`, `lemma`, `meaning_in_context`, `source_sentence`, `context_note`가 포함되는지 확인
- 그래프가 LangGraph로 연결되어 있고 최소 2개 노드를 가지는지 확인
- Notebook 안에 설계 문서와 코드가 모두 포함되어 있는지 확인
- 빈 입력일 때는 빈 결과를 반환하거나 간단한 안내 성격의 결과로 처리하는지 확인

## Run Notes

- 현재 저장소에는 원래 `langgraph` 의존성이 없었기 때문에 `pyproject.toml`에 추가한다.
- 실행 전 의존성 설치가 필요하다.

예시:

```bash
uv sync
uv run jupyter notebook
```

## Completion Criteria

이번 과제의 완료 기준은 아래와 같다.

- LangGraph를 사용한다.
- 최소 2개의 functioning node를 구현한다.
- 설계 문서와 코드를 Jupyter Notebook에 함께 포함한다.
- 입력 텍스트를 받아 구조화된 단어장 결과를 생성한다.

영속 저장과 검색 기능은 차기 확장 범위로 남긴다.
