from google.adk.agents.callback_context import CallbackContext
from google.adk.agents import Agent

from .prompt import STORY_WRITER_AGENT_DESCRIPTION, STORY_WRITER_AGENT_INSTRUCTION
from .settings import STORY_WRITER_MODEL
from .state import (
    STORYBOOK_STATE_KEY,
    TEMP_STORY_DRAFT_STATE_KEY,
    GeneratedStory,
    create_empty_storybook_state,
    create_storybook_state_from_generated_story,
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
        generated_story = GeneratedStory.model_validate_json(raw_story_draft)
    except Exception:
        return None

    callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_from_generated_story(
        generated_story
    )
    callback_context.state[TEMP_STORY_DRAFT_STATE_KEY] = raw_story_draft
    return None


story_writer_agent = Agent(
    name="StoryWriterAgent",
    model=STORY_WRITER_MODEL,
    description=STORY_WRITER_AGENT_DESCRIPTION,
    instruction=STORY_WRITER_AGENT_INSTRUCTION,
    before_agent_callback=ensure_storybook_state,
    output_key=TEMP_STORY_DRAFT_STATE_KEY,
    after_agent_callback=persist_generated_story,
)

root_agent = story_writer_agent
