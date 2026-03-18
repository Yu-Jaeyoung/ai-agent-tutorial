from typing import Literal

from pydantic import BaseModel, Field


STORYBOOK_STATE_KEY = "storybook"
TEMP_STORY_DRAFT_STATE_KEY = "temp:story_writer_story_draft"


class GeneratedStoryPage(BaseModel):
    page_number: int = Field(ge=1, le=5)
    page_text: str
    visual_description: str


class GeneratedStory(BaseModel):
    theme: str
    pages: list[GeneratedStoryPage] = Field(min_length=5, max_length=5)


class StoryPageState(BaseModel):
    page_number: int
    page_text: str = ""
    visual_description: str = ""
    image_ref: str | None = None


class StorybookState(BaseModel):
    theme: str = ""
    status: Literal[
        "waiting_for_theme",
        "theme_received",
        "story_ready",
        "illustration_ready",
        "failed",
    ] = "waiting_for_theme"
    pages: list[StoryPageState] = Field(default_factory=list)
    error: str | None = None


def create_empty_storybook_state() -> dict:
    return StorybookState().model_dump()


def create_storybook_state_for_theme(theme: str) -> dict:
    return StorybookState(theme=theme, status="theme_received").model_dump()


def create_storybook_state_from_generated_story(generated_story: GeneratedStory) -> dict:
    return StorybookState(
        theme=generated_story.theme,
        status="story_ready",
        pages=[
            StoryPageState(
                page_number=page.page_number,
                page_text=page.page_text,
                visual_description=page.visual_description,
                image_ref=None,
            )
            for page in generated_story.pages
        ],
        error=None,
    ).model_dump()
