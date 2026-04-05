# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI agent tutorial repository with 13 progressive challenges teaching agent architecture patterns across multiple frameworks: OpenAI Agents SDK, Google ADK, and Gemini + LangGraph. Each challenge is a self-contained mini-project.

## Common Commands

```bash
# Install dependencies
uv sync

# Run Streamlit apps (challenges 8, 13, 14)
uv run streamlit run challenge/8/run.py
uv run streamlit run challenge/13/run.py
uv run streamlit run challenge/14/run.py

# Run Google ADK web console (challenge 10)
uv run adk web challenge/10

# Run Jupyter notebooks (challenges 1-3, 11-12)
uv run jupyter notebook

# Run standalone scripts (challenges 4-7)
uv run python challenge/N/main.py

# Smoke tests
uv run python challenge/13/smoke_test.py
uv run python challenge/14/smoke_test.py
```

## Architecture

### Challenge Progression

| Challenges | Format | Framework | Pattern |
|------------|--------|-----------|---------|
| 1-3 | Jupyter notebooks | OpenAI API | Basic LLM/agent concepts |
| 4-7 | Python scripts | OpenAI API + SQLite | Stateful chat with memory |
| 8 | Streamlit app | OpenAI Agents SDK | Multi-agent with handoffs & guardrails |
| 9-10 | Google ADK app | Google ADK | Orchestrator-workers with parallel execution |
| 11-12 | Jupyter notebooks | Gemini + LangGraph | Educational agent (LeXi) with tools & memory |
| 13 | Streamlit app | Gemini + LangGraph | Production LeXi with service layer |
| 14 | Streamlit app | Gemini + LangGraph | LeXi polished: user auth, guardrails, UX, deploy |

### Key Agent Patterns

- **Multi-agent handoffs** (challenge 8): Triage agent routes to specialists (menu, order, reservation, complaints). Handoff callbacks in `restaurant_bot/handoffs.py`, agent wiring in `bot_agents/__init__.py`.
- **Orchestrator-workers** (challenge 10): Central coordinator dispatches parallel illustration tasks via Send API. All in `story_book_maker/agent.py`.
- **Custom LangGraph state** (challenges 11-13): Uses TypedDict state (not MessagesState) with conditional edge routing for domain-specific workflows. Graph defined in `lexi_app/graph.py`, nodes in `lexi_app/nodes.py`.
- **Tool-driven workflows** (challenges 12-13): Deterministic tools (`locate_source_sentences`, `select_review_candidates`) augment LLM reasoning. Defined in `lexi_app/tools.py`.

### Production App Structure (Challenges 8, 13)

Both production apps follow the same package pattern:
- `run.py` — Streamlit entry point
- `app.py` — UI logic and session state
- `state.py` / `models.py` — Pydantic models or TypedDicts
- `memory.py` / SQLite — Persistent storage (conversation history or vocabulary)
- `service.py` / `conversation_flow.py` — Orchestration layer

## Environment

- **Python**: >=3.13
- **Package manager**: uv (with `uv.lock` for deterministic installs)
- **API keys**: Loaded from `.env` via `python-dotenv` (OPENAI_API_KEY, GOOGLE_API_KEY)
- **Type checking**: Pyright configured in `pyrightconfig.json` — update the `include` and `executionEnvironments` paths when switching active challenge
- **SQLite databases**: `challenge/8/restaurant-bot-memory.db`, `challenge/13/lexi_memory.db`, `challenge/14/lexi_memory.db` are gitignored
