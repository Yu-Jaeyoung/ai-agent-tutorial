from typing import Literal

from pydantic import BaseModel, Field, model_validator


STORYBOOK_STATE_KEY = "storybook"
TEMP_STORY_DRAFT_STATE_KEY = "temp:story_writer_story_draft"


class GeneratedStoryPage(BaseModel):
    page_number: int = Field(ge=1, le=5)
    page_text: str
    visual_description: str


class GeneratedStory(BaseModel):
    theme: str
    pages: list[GeneratedStoryPage] = Field(min_length=5, max_length=5)


class StoryWriterResponse(BaseModel):
    status: Literal["needs_theme", "story_ready"]
    message: str
    theme: str = ""
    pages: list[GeneratedStoryPage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_story_shape(self):
        if self.status == "story_ready":
            if not self.theme.strip():
                raise ValueError("theme must be present when the story is ready.")
            if len(self.pages) != 5:
                raise ValueError("story_ready responses must include exactly 5 pages.")
        else:
            if self.pages:
                raise ValueError("needs_theme responses must not include story pages.")
        return self


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


def create_generated_story_from_writer_response(
    writer_response: StoryWriterResponse,
) -> GeneratedStory:
    return GeneratedStory(
        theme=writer_response.theme,
        pages=writer_response.pages,
    )


def load_storybook_state(raw_storybook: object | None) -> StorybookState:
    if not isinstance(raw_storybook, dict):
        return StorybookState()
    return StorybookState.model_validate(raw_storybook)
