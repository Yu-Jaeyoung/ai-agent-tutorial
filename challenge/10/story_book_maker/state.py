from typing import Literal, Mapping

from pydantic import BaseModel, Field, model_validator


STORYBOOK_STATE_KEY = "storybook"
TEMP_STORY_DRAFT_STATE_KEY = "temp:story_writer_story_draft"
PAGE_IMAGE_REF_STATE_KEY_PREFIX = "storybook:page_image_ref:"


class GeneratedStoryPage(BaseModel):
    page_number: int = Field(ge=1, le=5)
    page_text: str
    visual_description: str


class GeneratedStory(BaseModel):
    title: str
    theme: str
    pages: list[GeneratedStoryPage] = Field(min_length=5, max_length=5)


class StoryWriterResponse(BaseModel):
    status: Literal["needs_theme", "story_ready"]
    message: str
    title: str = ""
    theme: str = ""
    pages: list[GeneratedStoryPage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_story_shape(self):
        if self.status == "story_ready":
            if not self.title.strip():
                raise ValueError("title must be present when the story is ready.")
            if not self.theme.strip():
                raise ValueError("theme must be present when the story is ready.")
            if len(self.pages) != 5:
                raise ValueError("story_ready responses must include exactly 5 pages.")
        else:
            if self.title.strip():
                raise ValueError("needs_theme responses must not include a story title.")
            if self.pages:
                raise ValueError("needs_theme responses must not include story pages.")
        return self


class StoryPageState(BaseModel):
    page_number: int
    page_text: str = ""
    visual_description: str = ""
    image_ref: str | None = None


class StorybookState(BaseModel):
    title: str = ""
    theme: str = ""
    status: Literal[
        "waiting_for_theme",
        "theme_received",
        "story_ready",
        "illustration_in_progress",
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
        title=generated_story.title,
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
        title=writer_response.title,
        theme=writer_response.theme,
        pages=writer_response.pages,
    )


def load_storybook_state(raw_storybook: object | None) -> StorybookState:
    if not isinstance(raw_storybook, dict):
        return StorybookState()
    return StorybookState.model_validate(raw_storybook)


def create_illustration_ready_storybook_state(
    raw_storybook: object | None,
    image_refs: list[str],
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    if len(storybook_state.pages) != len(image_refs):
        raise ValueError("image_refs length must match the current story pages.")

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        status="illustration_ready",
        pages=[
            StoryPageState(
                page_number=page.page_number,
                page_text=page.page_text,
                visual_description=page.visual_description,
                image_ref=image_ref,
            )
            for page, image_ref in zip(storybook_state.pages, image_refs, strict=True)
        ],
        error=None,
    ).model_dump()


def create_storybook_state_with_page_image_ref(
    raw_storybook: object | None,
    page_number: int,
    image_ref: str,
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)

    updated_pages = []
    for page in storybook_state.pages:
        updated_pages.append(
            StoryPageState(
                page_number=page.page_number,
                page_text=page.page_text,
                visual_description=page.visual_description,
                image_ref=image_ref if page.page_number == page_number else page.image_ref,
            )
        )

    status = (
        "illustration_ready"
        if updated_pages and all(page.image_ref for page in updated_pages)
        else "illustration_in_progress"
    )

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        status=status,
        pages=updated_pages,
        error=None,
    ).model_dump()


def build_page_image_ref_state_key(page_number: int) -> str:
    return f"{PAGE_IMAGE_REF_STATE_KEY_PREFIX}{page_number}"


def extract_page_image_refs(raw_state: Mapping[str, object], total_pages: int) -> dict[int, str]:
    image_refs: dict[int, str] = {}
    for page_number in range(1, total_pages + 1):
        image_ref = raw_state.get(build_page_image_ref_state_key(page_number))
        if isinstance(image_ref, str) and image_ref.strip():
            image_refs[page_number] = image_ref
    return image_refs


def create_storybook_state_from_page_image_refs(
    raw_storybook: object | None,
    image_refs: Mapping[int, str],
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    updated_pages = []
    for page in storybook_state.pages:
        updated_pages.append(
            StoryPageState(
                page_number=page.page_number,
                page_text=page.page_text,
                visual_description=page.visual_description,
                image_ref=image_refs.get(page.page_number),
            )
        )

    status = (
        "illustration_ready"
        if updated_pages and all(page.image_ref for page in updated_pages)
        else "illustration_in_progress"
    )

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        status=status,
        pages=updated_pages,
        error=None,
    ).model_dump()


def create_storybook_state_with_status(
    raw_storybook: object | None,
    status: Literal[
        "waiting_for_theme",
        "theme_received",
        "story_ready",
        "illustration_in_progress",
        "illustration_ready",
        "failed",
    ],
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        status=status,
        pages=storybook_state.pages,
        error=storybook_state.error,
    ).model_dump()


def create_failed_storybook_state(
    raw_storybook: object | None,
    error: str,
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        status="failed",
        pages=storybook_state.pages,
        error=error,
    ).model_dump()
