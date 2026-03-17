from typing import Literal

from pydantic import BaseModel, Field


STORYBOOK_STATE_KEY = "storybook"


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
