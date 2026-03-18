from google.adk.agents.callback_context import CallbackContext
from google.adk.agents import Agent, SequentialAgent
from google.genai import types

from .prompt import (
    ILLUSTRATOR_AGENT_DESCRIPTION,
    ILLUSTRATOR_AGENT_INSTRUCTION,
    STORY_WRITER_AGENT_DESCRIPTION,
    STORY_WRITER_AGENT_INSTRUCTION,
)
from .settings import ILLUSTRATOR_MODEL, STORY_WRITER_MODEL
from .state import (
    STORYBOOK_STATE_KEY,
    TEMP_STORY_DRAFT_STATE_KEY,
    StoryWriterResponse,
    create_empty_storybook_state,
    create_generated_story_from_writer_response,
    create_storybook_state_from_generated_story,
    load_storybook_state,
)


def ensure_storybook_state(callback_context: CallbackContext):
    callback_context.state.setdefault(
        STORYBOOK_STATE_KEY,
        create_empty_storybook_state(),
    )
    return None


def persist_generated_story(callback_context: CallbackContext):
    raw_story_draft = callback_context.state.get(TEMP_STORY_DRAFT_STATE_KEY)
    if not isinstance(raw_story_draft, str) or not raw_story_draft.strip():
        return None

    try:
        writer_response = StoryWriterResponse.model_validate_json(raw_story_draft)
    except Exception:
        return None

    if writer_response.status == "needs_theme":
        callback_context.state[STORYBOOK_STATE_KEY] = create_empty_storybook_state()
        return None

    generated_story = create_generated_story_from_writer_response(writer_response)
    callback_context.state[STORYBOOK_STATE_KEY] = (
        create_storybook_state_from_generated_story(generated_story)
    )
    callback_context.state[TEMP_STORY_DRAFT_STATE_KEY] = raw_story_draft
    return None


def build_illustrator_instruction(readonly_context):
    storybook_state = load_storybook_state(readonly_context.state.get(STORYBOOK_STATE_KEY))

    if storybook_state.status != "story_ready" or len(storybook_state.pages) != 5:
        return (
            f"{ILLUSTRATOR_AGENT_INSTRUCTION}\n\n"
            "Current storybook state: story data is not ready for illustration yet."
        )

    page_summaries = "\n".join(
        (
            f"- Page {page.page_number}: "
            f"text={page.page_text!r}, "
            f"visual_description={page.visual_description!r}"
        )
        for page in storybook_state.pages
    )

    return (
        f"{ILLUSTRATOR_AGENT_INSTRUCTION}\n\n"
        f"Current theme: {storybook_state.theme!r}\n"
        "Current pages ready for illustration:\n"
        f"{page_summaries}"
    )


story_writer_agent = Agent(
    name="StoryWriterAgent",
    model=STORY_WRITER_MODEL,
    description=STORY_WRITER_AGENT_DESCRIPTION,
    instruction=STORY_WRITER_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2,
    ),
    before_agent_callback=ensure_storybook_state,
    output_key=TEMP_STORY_DRAFT_STATE_KEY,
    after_agent_callback=persist_generated_story,
)

illustrator_agent = Agent(
    name="IllustratorAgent",
    model=ILLUSTRATOR_MODEL,
    description=ILLUSTRATOR_AGENT_DESCRIPTION,
    instruction=build_illustrator_instruction,
)

root_agent = SequentialAgent(
    name="StoryBookWorkflow",
    description="Runs story writing first and then passes the shared state to the illustrator stage.",
    sub_agents=[story_writer_agent, illustrator_agent],
)
