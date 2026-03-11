# Challenge 8

이 문서는 `challenge/8` 과제에서 합의가 끝난 요구사항과 결론만 간단히 기록한다.
새로운 질문이 생기면 결론이 난 내용만 여기에 추가한다.

## Goal

OpenAI Agents SDK를 사용해 식당 상담용 멀티 에이전트 챗봇을 구성한다.

## Core Requirements

- 에이전트는 `Triage`, `Menu`, `Order`, `Reservation` 4개로 구성한다.
- `Triage Agent`가 사용자의 첫 진입점이다.
- `Triage Agent`는 사용자 의도를 판단하고 OpenAI SDK `handoff`로 적절한 에이전트에 연결한다.
- `Menu`, `Order`, `Reservation` 에이전트는 자신의 범위를 벗어난 요청을 받으면 다시 적절한 에이전트로 handoff한다.
- 각 에이전트의 동작 기준은 `instruction.py`에 정의된 instructions를 사용한다.
- `Menu Agent`는 샘플 메뉴 데이터 `menu_list`를 기반으로 메뉴 관련 질문에 답한다.

## Settled Decisions

### Agent Instructions

- instruction은 OpenAI SDK `Agent(..., instructions=...)`에 바로 넣을 수 있는 문자열 형태로 유지한다.
- 현재 instruction 길이는 `gpt-4o-mini`에 사용하기에 충분히 짧다.
- `Menu Agent`는 `f"{menu_agent_instruction}\n\n{menu_list}"` 형태로 instruction과 메뉴 데이터를 합쳐 사용한다.

### Package Structure

- `challenge/8`은 독립적인 mini-project처럼 다룬다.
- 실행 진입점은 `run.py` 하나로 둔다.
- 실제 앱 코드는 `restaurant_bot/` 패키지 아래에 둔다.
- 패키지 내부 모듈끼리는 상대 import를 사용한다.
- 패키지 바깥 진입점인 `run.py`는 절대 import를 사용한다.

### IDE / Pyright

- `pyrightconfig.json`은 현재 작업 중인 challenge 하나만 가리킨다.
- 현재 활성 challenge는 `challenge/8`이다.
- 이후 `challenge/9`를 작업할 때는 기존 설정에 추가하지 말고, 활성 root를 `challenge/9`로 교체한다.

### Handoff Implementation

- 각 `*agent.py` 파일은 자기 `Agent` 정의만 가진다.
- 에이전트 간 handoff wiring은 `restaurant_bot/bot_agents/__init__.py`에서 중앙 관리한다.
- 공통 handoff callback 로직은 `restaurant_bot/handoffs.py`에 둔다.
- handoff 이벤트는 Streamlit UI에서 표시할 수 있도록 `st.session_state`에 기록한다.
- handoff callback 입력 모델은 `HandoffData`를 사용한다.

### App Behavior

- `app.py`는 `triage_agent`를 시작점으로 `Runner.run_streamed()`를 실행한다.
- 대화 히스토리는 `SQLiteSession`으로 유지한다.
- 세션 DB 파일은 `challenge/8/customer-support-memory.db`에 고정한다.
- handoff trace는 `[From Agent -> To Agent]` 형식의 bold 텍스트로 보여준다.
- 현재 턴과 이전 턴의 handoff trace를 UI에서 유지한다.
- 사이드바에서 샘플 메뉴 데이터와 세션 상태를 확인하고 reset할 수 있다.

## Current Structure

```text
challenge/8/
  README.md
  run.py
  restaurant_bot/
    app.py
    instruction.py
    models.py
    handoffs.py
    bot_agents/
      __init__.py
      triage_agent.py
      menu_agent.py
      order_agent.py
      reservation_agent.py
```

## Run

```bash
cd challenge/8
streamlit run run.py
```

## Next Update Rule

- README에는 질문 자체보다 결론만 기록한다.
- 설명은 짧게 유지하고, 구현에 영향을 주는 결정만 남긴다.
