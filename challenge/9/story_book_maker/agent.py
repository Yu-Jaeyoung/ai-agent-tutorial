import re
from pathlib import Path

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
    GENERATED_IMAGES_DIR,
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
        return None

    generated_story = create_generated_story_from_writer_response(writer_response)
    callback_context.state[STORYBOOK_STATE_KEY] = (
        create_storybook_state_from_generated_story(generated_story)
    )
    callback_context.state[TEMP_STORY_DRAFT_STATE_KEY] = raw_story_draft
    return None


def build_text_content(message: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=message)])


def slugify_theme(theme: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
    return slug or "storybook"


def build_illustration_output_dir(theme: str) -> Path:
    output_dir = GENERATED_IMAGES_DIR / slugify_theme(theme)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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


def extract_generated_image(response) -> object:
    for part in response.parts or []:
        try:
            return part.as_image()
        except Exception:
            continue
    raise ValueError("The image model response did not contain a generated image.")


def generate_page_illustration(
    client: Client,
    theme: str,
    page: StoryPageState,
    output_dir: Path,
) -> str:
    response = client.models.generate_content(
        model=ILLUSTRATOR_MODEL,
        contents=build_page_illustration_prompt(theme, page),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=ILLUSTRATION_ASPECT_RATIO,
                output_mime_type="image/png",
            ),
        ),
    )
    image = extract_generated_image(response)
    image_path = output_dir / f"page_{page.page_number}.png"
    image.save(image_path)
    return str(image_path.resolve())


def summarize_image_refs(storybook_state) -> str:
    page_lines = "\n".join(
        f"- Page {page.page_number}: image_ref={page.image_ref!r}"
        for page in storybook_state.pages
    )
    return (
        "Illustrations are ready and image_ref values were stored in shared state.\n"
        f"{page_lines}"
    )


def generate_storybook_illustrations(callback_context: CallbackContext):
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
        output_dir = build_illustration_output_dir(storybook_state.theme)
        image_refs = [
            generate_page_illustration(client, storybook_state.theme, page, output_dir)
            for page in storybook_state.pages
        ]
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
    return None


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
