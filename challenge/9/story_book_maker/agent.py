import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents import Agent, SequentialAgent
from google.genai import Client, types

from .prompt import (
    ILLUSTRATOR_AGENT_DESCRIPTION,
    ILLUSTRATOR_AGENT_INSTRUCTION,
    STORY_WRITER_AGENT_DESCRIPTION,
    STORY_WRITER_AGENT_INSTRUCTION,
)
from .settings import (
    GOOGLE_API_KEY,
    ILLUSTRATION_ASPECT_RATIO,
    ILLUSTRATOR_MODEL,
    STORY_WRITER_MODEL,
)
from .state import (
    STORYBOOK_STATE_KEY,
    TEMP_STORY_DRAFT_STATE_KEY,
    StoryWriterResponse,
    StoryPageState,
    create_failed_storybook_state,
    create_empty_storybook_state,
    create_generated_story_from_writer_response,
    create_illustration_ready_storybook_state,
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
        return build_text_content(writer_response.message)

    generated_story = create_generated_story_from_writer_response(writer_response)
    callback_context.state[STORYBOOK_STATE_KEY] = (
        create_storybook_state_from_generated_story(generated_story)
    )
    callback_context.state[TEMP_STORY_DRAFT_STATE_KEY] = raw_story_draft
    return build_text_content(summarize_story_ready(generated_story.theme))


def build_text_content(message: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=message)])


def summarize_story_ready(theme: str) -> str:
    return (
        f"Created a 5-page story for '{theme}'.\n"
        "Starting the illustration step now."
    )


def slugify_theme(theme: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
    return slug or "storybook"


def build_page_illustration_prompt(theme: str, page: StoryPageState) -> str:
    return f"""
Create one children's storybook illustration for a single page.

Theme: {theme}
Page number: {page.page_number}
Story text: {page.page_text}
Visual description: {page.visual_description}

Requirements:
- Make the image child-friendly, warm, and expressive.
- Keep the characters and visual style consistent across all pages for the same theme.
- Do not include captions, speech bubbles, or printed text inside the image.
- Focus on a clear picture-book composition for this page only.
""".strip()


def build_page_artifact_basename(theme: str, page_number: int) -> str:
    return f"{slugify_theme(theme)}-page-{page_number}-image"


def find_existing_page_artifact(
    existing_artifacts: list[str],
    theme: str,
    page_number: int,
) -> str | None:
    artifact_prefix = f"{build_page_artifact_basename(theme, page_number)}."
    for artifact_name in sorted(existing_artifacts):
        if artifact_name.startswith(artifact_prefix):
            return artifact_name
    return None


def mime_type_to_extension(mime_type: str) -> str:
    normalized_mime_type = mime_type.lower()
    if normalized_mime_type == "image/png":
        return ".png"
    if normalized_mime_type in {"image/jpeg", "image/jpg"}:
        return ".jpeg"
    if normalized_mime_type == "image/webp":
        return ".webp"
    return ".img"


def extract_generated_image_bytes(response) -> tuple[bytes, str]:
    for candidate in response.candidates or []:
        if not candidate.content:
            continue

        for part in candidate.content.parts or []:
            inline_data = part.inline_data
            if inline_data and inline_data.data:
                return inline_data.data, inline_data.mime_type or "image/jpeg"

    raise ValueError("The image model response did not contain generated image bytes.")


def generate_page_illustration(
    client: Client,
    theme: str,
    page: StoryPageState,
    existing_artifacts: list[str],
) -> tuple[str, types.Part | None]:
    existing_artifact = find_existing_page_artifact(
        existing_artifacts=existing_artifacts,
        theme=theme,
        page_number=page.page_number,
    )
    if existing_artifact:
        return existing_artifact, None

    response = client.models.generate_content(
        model=ILLUSTRATOR_MODEL,
        contents=[build_page_illustration_prompt(theme, page)],
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            image_config=types.ImageConfig(
                aspect_ratio=ILLUSTRATION_ASPECT_RATIO,
            ),
        ),
    )
    image_bytes, mime_type = extract_generated_image_bytes(response)
    artifact_filename = (
        f"{build_page_artifact_basename(theme, page.page_number)}"
        f"{mime_type_to_extension(mime_type)}"
    )
    artifact = types.Part(
        inline_data=types.Blob(
            data=image_bytes,
            mime_type=mime_type,
        )
    )
    return artifact_filename, artifact


def summarize_image_refs(storybook_state) -> str:
    page_lines = "\n".join(
        f"- Page {page.page_number}: {page.image_ref}"
        for page in storybook_state.pages
    )
    return (
        f"Illustrations are ready for '{storybook_state.theme}'.\n"
        "Saved image references:\n"
        f"{page_lines}"
    )


async def generate_storybook_illustrations(callback_context: CallbackContext):
    storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))

    if (
        storybook_state.status == "illustration_ready"
        and len(storybook_state.pages) == 5
        and all(page.image_ref for page in storybook_state.pages)
    ):
        return build_text_content(summarize_image_refs(storybook_state))

    if storybook_state.status != "story_ready" or len(storybook_state.pages) != 5:
        return build_text_content("Illustration data is not ready yet.")

    try:
        client = Client(api_key=GOOGLE_API_KEY)
        existing_artifacts = await callback_context.list_artifacts()
        image_refs: list[str] = []
        for page in storybook_state.pages:
            artifact_filename, artifact = generate_page_illustration(
                client=client,
                theme=storybook_state.theme,
                page=page,
                existing_artifacts=existing_artifacts,
            )
            if artifact is not None:
                await callback_context.save_artifact(
                    filename=artifact_filename,
                    artifact=artifact,
                )
                existing_artifacts.append(artifact_filename)
            image_refs.append(artifact_filename)
    except Exception as error:
        callback_context.state[STORYBOOK_STATE_KEY] = create_failed_storybook_state(
            callback_context.state.get(STORYBOOK_STATE_KEY),
            f"illustration_generation_failed: {error}",
        )
        return build_text_content(
            "Illustration generation failed. The shared storybook state is now marked as failed."
        )

    callback_context.state[STORYBOOK_STATE_KEY] = create_illustration_ready_storybook_state(
        callback_context.state.get(STORYBOOK_STATE_KEY),
        image_refs,
    )
    return build_text_content(
        summarize_image_refs(
            load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))
        )
    )


def build_illustrator_instruction(readonly_context):
    storybook_state = load_storybook_state(readonly_context.state.get(STORYBOOK_STATE_KEY))

    if storybook_state.status == "illustration_ready":
        return (
            f"{ILLUSTRATOR_AGENT_INSTRUCTION}\n\n"
            f"Current theme: {storybook_state.theme!r}\n"
            "Current stored image refs:\n"
            f"{summarize_image_refs(storybook_state)}"
        )

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
    before_agent_callback=generate_storybook_illustrations,
)

root_agent = SequentialAgent(
    name="StoryBookWorkflow",
    description="Runs story writing first and then passes the shared state to the illustrator stage.",
    sub_agents=[story_writer_agent, illustrator_agent],
)
