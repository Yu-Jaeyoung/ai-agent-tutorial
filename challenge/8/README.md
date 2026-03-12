# Challenge 8

이 문서는 `challenge/8` 과제에서 합의가 끝난 요구사항과 결론만 간단히 기록한다.
새로운 질문이 생기면 결론이 난 내용만 여기에 추가한다.

## Goal

OpenAI Agents SDK를 사용해 식당 상담용 멀티 에이전트 챗봇을 구성한다.

### Agent Instructions

- instruction은 OpenAI SDK `Agent(..., instructions=...)`에 바로 넣을 수 있는 문자열 형태로 유지한다.
- 현재 instruction 길이는 `gpt-4o-mini`에 사용하기에 충분히 짧다.
- `Menu Agent`는 `f"{menu_agent_instruction}\n\n{menu_list}"` 형태로 instruction과 메뉴 데이터를 합쳐 사용한다.
- `menu_list`는 구조화된 menu catalog에서 생성한 요약 문자열을 사용한다.
- `Menu Agent`와 `Order Agent`는 같은 menu tool을 사용해서 동일한 메뉴 원본 데이터를 조회한다.
- 

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
- Complaints Agent를 specialist로 추가하고 모든 business agent에서 complaints handoff를 지원한다.
- 마지막으로 응답한 agent를 Streamlit session state에 유지하고, 다음 턴은 그 agent를 시작점으로 이어간다.

### Guardrails

- 입력 guardrail은 모든 사용자 응답 agent 시작점에서 실행한다.
- 입력 guardrail은 대화 전체가 아니라 최신 user turn을 기준으로 판정한다.
- 입력 guardrail은 `pending_flow_state`와 직전 assistant 응답을 참고해 `확인`, `주문해줘`, `4명`, `그 메뉴` 같은 문맥형 follow-up을 허용한다.
- 레스토랑과 무관한 입력은 차단한다.
- 욕설이 있어도 레스토랑 complaint 맥락이면 허용한다.
- 음식, 직원, 서비스, 주문 같은 레스토랑 불만 맥락이 명확하면 거친 표현이 있어도 Complaints 흐름을 막지 않는다.
- 메뉴명 + 주문 의도, 메뉴 조회/추천/알레르기, 예약 같은 명시적 레스토랑 지원 요청은 deterministic allow path로 먼저 통과시킨다.
- 출력 guardrail은 모든 사용자 응답 agent에 적용한다.
- 내부 정보 노출이나 무례한 톤은 fallback 응답으로 대체한다.

### App Behavior

- 첫 진입은 `Triage Agent`에서 시작하고, 이후 턴은 현재 active agent를 시작점으로 `Runner.run_streamed()`를 실행한다.
- 대화 히스토리는 `SQLiteSession`으로 유지한다.
- specialist 흐름 유지를 위해 `pending_flow_state`를 Streamlit session state에 저장한다.
- 세션 DB 파일은 `challenge/8/restaurant-bot-memory.db`에 고정한다.
- 세션에 저장하는 assistant 메시지 content type은 `output_text`를 사용한다.
- 기존 세션 히스토리에 잘못 저장된 assistant content type은 앱 시작 시 정규화한다.
- 첫 화면 안내 문구는 기능 중심으로 작성하고, agent/handoff 같은 내부 구현 표현은 직접 노출하지 않는다.
- handoff trace는 `[From Agent -> To Agent]` 형식의 bold 텍스트로 보여준다.
- 현재 턴과 이전 턴의 handoff trace를 UI에서 유지한다.
- 응답이 진행 중일 때는 새 입력을 잠그고, 제출된 메시지는 순서대로 처리한다.
- 스트리밍 중인 응답도 세션 상태에 즉시 반영해서 다음 질문 후 사라지지 않게 유지한다.
- 주문과 예약이 완료되면 다음 턴 시작 agent는 다시 `Triage Agent`로 복귀한다.
- guardrail tripwire가 발생하면 raw exception 대신 fallback 응답을 채팅에 기록한다.
- 사이드바에서 샘플 메뉴 데이터와 세션 상태를 확인하고 reset할 수 있다.

## Current Structure

```text
challenge/8/
  README.md
  requirements.txt
  run.py
  restaurant_bot/
    app.py
    instruction.py
    models.py
    handoffs.py
    guardrails.py
    conversation_flow.py
    menu_catalog.py
    menu_tools.py
    bot_agents/
      __init__.py
      triage_agent.py
      menu_agent.py
      order_agent.py
      reservation_agent.py
      complaints_agent.py
```

## Run

```bash
streamlit run challenge/8/run.py
```

## Deploy

- 같은 GitHub 레포를 그대로 사용하고, Streamlit Community Cloud에서 `Main file path`를 `challenge/8/run.py`로 지정한다.
- `challenge/8/requirements.txt`는 엔트리 파일 옆에 있으므로 배포 시 자동으로 감지된다.
- `OPENAI_API_KEY`는 로컬에서는 `.env`, 배포 환경에서는 Streamlit `Secrets`에 등록한다.
- `restaurant-bot-memory.db`는 로컬 파일이므로 배포 환경에서는 재시작이나 재배포 후 유지되지 않을 수 있다.

배포 입력값 예시는 아래와 같다.

```text
Repository: <your-github-repo>
Branch: main
Main file path: challenge/8/run.py
Secrets:
OPENAI_API_KEY="your-api-key"
```

## Next Update Rule

- README에는 질문 자체보다 결론만 기록한다.
- 설명은 짧게 유지하고, 구현에 영향을 주는 결정만 남긴다.
