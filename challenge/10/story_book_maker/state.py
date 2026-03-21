import re
from typing import Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator


STORYBOOK_STATE_KEY = "storybook"
TEMP_STORY_DRAFT_STATE_KEY = "temp:story_writer_story_draft"
PAGE_ILLUSTRATION_REF_STATE_KEY_PREFIX = "storybook:page_illustration_ref:"
PAGE_IMAGE_REF_STATE_KEY_PREFIX = "storybook:page_image_ref:"


CharacterRole = Literal["protagonist", "supporting", "recurring_entity"]


class CharacterProfile(BaseModel):
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: CharacterRole
    appearance_summary: str = Field(min_length=1)
    visual_traits: list[str] = Field(default_factory=list)
    clothing_or_accessories: list[str] = Field(default_factory=list)
    signature_props: list[str] = Field(default_factory=list)
    continuity_rules: list[str] = Field(default_factory=list)

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value):
        if not isinstance(value, str):
            return value

        normalized = re.sub(r"[^a-z]+", "_", value.strip().lower()).strip("_")
        role_aliases = {
            "protagonist": "protagonist",
            "main_character": "protagonist",
            "main": "protagonist",
            "lead": "protagonist",
            "hero": "protagonist",
            "supporting": "supporting",
            "supporting_character": "supporting",
            "secondary": "supporting",
            "secondary_character": "supporting",
            "companion": "supporting",
            "recurring_entity": "recurring_entity",
            "recurring": "recurring_entity",
            "recurring_character": "recurring_entity",
            "entity": "recurring_entity",
            "central_entity": "recurring_entity",
        }
        return role_aliases.get(normalized, normalized)

    @model_validator(mode="after")
    def validate_profile_shape(self):
        if not self.character_id.strip():
            raise ValueError("character_id must not be blank.")
        if not self.name.strip():
            raise ValueError("character name must not be blank.")
        if not self.appearance_summary.strip():
            raise ValueError("appearance_summary must not be blank.")
        if not self.visual_traits:
            raise ValueError("visual_traits must include at least one trait.")
        if not self.continuity_rules:
            raise ValueError("continuity_rules must include at least one rule.")
        return self


def validate_character_collection(characters: list[CharacterProfile]) -> None:
    if not characters:
        raise ValueError("story_ready responses must include at least one character profile.")

    character_ids = [character.character_id for character in characters]
    if len(character_ids) != len(set(character_ids)):
        raise ValueError("character_id values must be unique.")

    if not any(
        character.role in {"protagonist", "recurring_entity"}
        for character in characters
    ):
        raise ValueError(
            "story_ready responses must include at least one protagonist or recurring_entity."
        )


def validate_page_featured_character_ids(
    pages: list["GeneratedStoryPage"],
    characters: list[CharacterProfile],
) -> None:
    character_ids = {character.character_id for character in characters}
    for page in pages:
        unknown_ids = [
            character_id
            for character_id in page.featured_character_ids
            if character_id not in character_ids
        ]
        if unknown_ids:
            raise ValueError(
                "featured_character_ids must match declared character_ids. "
                f"Unknown ids on page {page.page_number}: {', '.join(unknown_ids)}"
            )


class GeneratedStoryPage(BaseModel):
    page_number: int = Field(ge=1, le=5)
    page_text: str
    visual_description: str
    featured_character_ids: list[str] = Field(default_factory=list)


class GeneratedStory(BaseModel):
    title: str
    theme: str
    characters: list[CharacterProfile] = Field(min_length=1)
    pages: list[GeneratedStoryPage] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_story_consistency(self):
        validate_character_collection(self.characters)
        validate_page_featured_character_ids(self.pages, self.characters)
        return self


class StoryWriterResponse(BaseModel):
    status: Literal["needs_theme", "story_ready"]
    message: str
    title: str = ""
    theme: str = ""
    characters: list[CharacterProfile] = Field(default_factory=list)
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
            GeneratedStory(
                title=self.title,
                theme=self.theme,
                characters=self.characters,
                pages=self.pages,
            )
        else:
            if self.title.strip():
                raise ValueError("needs_theme responses must not include a story title.")
            if self.theme.strip():
                raise ValueError("needs_theme responses must not include a normalized theme.")
            if self.characters:
                raise ValueError("needs_theme responses must not include characters.")
            if self.pages:
                raise ValueError("needs_theme responses must not include story pages.")
        return self


class StoryPageState(BaseModel):
    page_number: int
    status: Literal[
        "pending",
        "illustration_in_progress",
        "illustration_ready",
        "failed",
    ] = "pending"
    page_text: str = ""
    visual_description: str = ""
    featured_character_ids: list[str] = Field(default_factory=list)
    illustration_ref: str | None = None
    page_image_ref: str | None = None
    image_ref: str | None = None
    error: str | None = None


class StorybookState(BaseModel):
    title: str = ""
    theme: str = ""
    characters: list[CharacterProfile] = Field(default_factory=list)
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
    failed_stage: str | None = None
    failed_page_number: int | None = None


def create_empty_storybook_state() -> dict:
    return StorybookState().model_dump()


def create_storybook_state_for_theme(theme: str) -> dict:
    return StorybookState(theme=theme, status="theme_received").model_dump()


def create_storybook_state_from_generated_story(generated_story: GeneratedStory) -> dict:
    return StorybookState(
        title=generated_story.title,
        theme=generated_story.theme,
        characters=generated_story.characters,
        status="story_ready",
        pages=[
            StoryPageState(
                page_number=page.page_number,
                status="pending",
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=None,
                page_image_ref=None,
                image_ref=None,
                error=None,
            )
            for page in generated_story.pages
        ],
        error=None,
        failed_stage=None,
        failed_page_number=None,
    ).model_dump()


def create_generated_story_from_writer_response(
    writer_response: StoryWriterResponse,
) -> GeneratedStory:
    return GeneratedStory(
        title=writer_response.title,
        theme=writer_response.theme,
        characters=writer_response.characters,
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
        characters=storybook_state.characters,
        status="illustration_ready",
        pages=[
            StoryPageState(
                page_number=page.page_number,
                status="illustration_ready",
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=None,
                page_image_ref=image_ref,
                image_ref=image_ref,
                error=None,
            )
            for page, image_ref in zip(storybook_state.pages, image_refs, strict=True)
        ],
        error=None,
        failed_stage=None,
        failed_page_number=None,
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
                status=(
                    "illustration_ready"
                    if page.page_number == page_number
                    else page.status
                ),
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=page.illustration_ref,
                page_image_ref=(
                    image_ref if page.page_number == page_number else page.page_image_ref
                ),
                image_ref=image_ref if page.page_number == page_number else page.image_ref,
                error=None if page.page_number == page_number else page.error,
            )
        )

    status = (
        "illustration_ready"
        if updated_pages and all(page.page_image_ref for page in updated_pages)
        else "illustration_in_progress"
    )

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        characters=storybook_state.characters,
        status=status,
        pages=updated_pages,
        error=None,
        failed_stage=None,
        failed_page_number=None,
    ).model_dump()


def build_page_illustration_ref_state_key(page_number: int) -> str:
    return f"{PAGE_ILLUSTRATION_REF_STATE_KEY_PREFIX}{page_number}"


def build_page_image_ref_state_key(page_number: int) -> str:
    return f"{PAGE_IMAGE_REF_STATE_KEY_PREFIX}{page_number}"


def extract_page_artifact_refs(
    raw_state: Mapping[str, object],
    total_pages: int,
    key_builder,
) -> dict[int, str]:
    image_refs: dict[int, str] = {}
    for page_number in range(1, total_pages + 1):
        image_ref = raw_state.get(key_builder(page_number))
        if isinstance(image_ref, str) and image_ref.strip():
            image_refs[page_number] = image_ref
    return image_refs


def extract_page_illustration_refs(
    raw_state: Mapping[str, object],
    total_pages: int,
) -> dict[int, str]:
    return extract_page_artifact_refs(
        raw_state=raw_state,
        total_pages=total_pages,
        key_builder=build_page_illustration_ref_state_key,
    )


def extract_page_image_refs(
    raw_state: Mapping[str, object],
    total_pages: int,
) -> dict[int, str]:
    return extract_page_artifact_refs(
        raw_state=raw_state,
        total_pages=total_pages,
        key_builder=build_page_image_ref_state_key,
    )


def create_storybook_state_from_page_image_refs(
    raw_storybook: object | None,
    image_refs: Mapping[int, str],
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    return create_storybook_state_from_page_asset_refs(
        raw_storybook=raw_storybook,
        illustration_refs={
            page.page_number: page.illustration_ref
            for page in storybook_state.pages
            if page.illustration_ref
        },
        page_image_refs=image_refs,
    )


def create_storybook_state_from_page_asset_refs(
    raw_storybook: object | None,
    illustration_refs: Mapping[int, str],
    page_image_refs: Mapping[int, str],
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    updated_pages = []
    for page in storybook_state.pages:
        updated_pages.append(
            StoryPageState(
                page_number=page.page_number,
                status=(
                    "illustration_ready"
                    if page_image_refs.get(page.page_number)
                    else (
                        "illustration_in_progress"
                        if illustration_refs.get(page.page_number)
                        else page.status
                    )
                ),
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=illustration_refs.get(page.page_number)
                or page.illustration_ref,
                page_image_ref=page_image_refs.get(page.page_number)
                or page.page_image_ref,
                image_ref=page_image_refs.get(page.page_number) or page.image_ref,
                error=None if page_image_refs.get(page.page_number) else page.error,
            )
        )

    status = (
        "illustration_ready"
        if updated_pages and all(page.page_image_ref for page in updated_pages)
        else "illustration_in_progress"
    )

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        characters=storybook_state.characters,
        status=status,
        pages=updated_pages,
        error=None,
        failed_stage=None,
        failed_page_number=None,
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
        characters=storybook_state.characters,
        status=status,
        pages=storybook_state.pages,
        error=storybook_state.error,
        failed_stage=storybook_state.failed_stage,
        failed_page_number=storybook_state.failed_page_number,
    ).model_dump()


def create_storybook_state_with_page_status(
    raw_storybook: object | None,
    page_number: int,
    status: Literal[
        "pending",
        "illustration_in_progress",
        "illustration_ready",
        "failed",
    ],
    error: str | None = None,
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    updated_pages = []
    for page in storybook_state.pages:
        updated_pages.append(
            StoryPageState(
                page_number=page.page_number,
                status=status if page.page_number == page_number else page.status,
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=page.illustration_ref,
                page_image_ref=page.page_image_ref,
                image_ref=page.image_ref,
                error=error if page.page_number == page_number else page.error,
            )
        )

    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        characters=storybook_state.characters,
        status=storybook_state.status,
        pages=updated_pages,
        error=storybook_state.error,
        failed_stage=storybook_state.failed_stage,
        failed_page_number=storybook_state.failed_page_number,
    ).model_dump()


def create_failed_storybook_state(
    raw_storybook: object | None,
    error: str,
    *,
    stage: str | None = None,
    page_number: int | None = None,
) -> dict:
    storybook_state = load_storybook_state(raw_storybook)
    updated_pages = []
    for page in storybook_state.pages:
        updated_pages.append(
            StoryPageState(
                page_number=page.page_number,
                status=(
                    "failed"
                    if page_number is not None and page.page_number == page_number
                    else page.status
                ),
                page_text=page.page_text,
                visual_description=page.visual_description,
                featured_character_ids=page.featured_character_ids,
                illustration_ref=page.illustration_ref,
                page_image_ref=page.page_image_ref,
                image_ref=page.image_ref,
                error=(
                    error
                    if page_number is not None and page.page_number == page_number
                    else page.error
                ),
            )
        )
    return StorybookState(
        title=storybook_state.title,
        theme=storybook_state.theme,
        characters=storybook_state.characters,
        status="failed",
        pages=updated_pages,
        error=error,
        failed_stage=stage,
        failed_page_number=page_number,
    ).model_dump()
