import hashlib
import json
import re
from pathlib import Path

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.genai import Client, types

from .page_compositor import compose_storybook_page
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
    StoryWriterResponse,
    StoryPageState,
    build_page_illustration_ref_state_key,
    build_page_image_ref_state_key,
    create_failed_storybook_state,
    create_empty_storybook_state,
    create_generated_story_from_writer_response,
    create_storybook_state_from_page_asset_refs,
    create_storybook_state_with_page_status,
    create_storybook_state_from_page_image_refs,
    create_storybook_state_with_status,
    create_storybook_state_from_generated_story,
    extract_page_illustration_refs,
    extract_page_image_refs,
    load_storybook_state,
)


def ensure_storybook_state(callback_context: CallbackContext):
    callback_context.state.setdefault(
        STORYBOOK_STATE_KEY,
        create_empty_storybook_state(),
    )
    return None


def build_text_content(message: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=message)])


def build_empty_content() -> types.Content:
    return types.Content(role="model", parts=[])


def announce_story_writing_started(callback_context: CallbackContext):
    return build_text_content("스토리 작성 중...")


def summarize_story_ready(theme: str) -> str:
    return f"'{theme}' 테마로 5페이지 동화를 완성했습니다. 이제 삽화를 생성합니다."


def summarize_page_illustration_started(page_number: int) -> str:
    return f"이미지 {page_number}/5 생성 중..."


def summarize_page_illustration_completed(page_number: int) -> str:
    return f"이미지 {page_number}/5 생성 완료"


def clear_page_asset_refs(callback_context: CallbackContext, total_pages: int = 5):
    for page_number in range(1, total_pages + 1):
        callback_context.state[build_page_illustration_ref_state_key(page_number)] = ""
        callback_context.state[build_page_image_ref_state_key(page_number)] = ""


def slugify_theme(theme: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
    if slug:
        return slug
    digest = hashlib.sha256(theme.encode("utf-8")).hexdigest()
    return f"storybook-{digest[:8]}"


def build_local_output_dir(theme: str) -> Path:
    output_dir = GENERATED_IMAGES_DIR / slugify_theme(theme)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_local_asset_path(
    theme: str,
    page_number: int,
    asset_name: str,
    mime_type: str,
) -> Path:
    return build_local_output_dir(theme) / f"{asset_name}_page_{page_number}{mime_type_to_extension(mime_type)}"


def save_local_image_bytes(
    theme: str,
    page_number: int,
    asset_name: str,
    image_bytes: bytes,
    mime_type: str,
) -> str:
    image_path = build_local_asset_path(theme, page_number, asset_name, mime_type)
    image_path.write_bytes(image_bytes)
    return str(image_path.resolve())


def build_storybook_style_guide() -> str:
    return """
Shared art direction:
- Create a cohesive children's picture-book series in the same hand-painted watercolor storybook style.
- Use soft warm lighting, gentle textures, rounded shapes, and a calm pastel color palette.
- Keep recurring characters, props, and environments visually identical across every page.
- Preserve the same face shapes, body proportions, colors, clothing, accessories, and important props on all pages.
- Maintain consistent world design, camera language, brushwork, and emotional tone across the whole book.
- If a detail is not explicitly repeated on a page, preserve it from the other pages instead of inventing a new variation.
- The five illustrations must feel like consecutive spreads from one book, not separate unrelated images.
""".strip()


def build_storybook_overview(storybook_state) -> str:
    return "\n".join(
        (
            f"Page {page.page_number}: "
            f"text={page.page_text!r}; "
            f"visual_description={page.visual_description!r}"
        )
        for page in storybook_state.pages
    )


def build_theme_seed(theme: str) -> int:
    digest = hashlib.sha256(theme.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def format_display_text(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def extract_user_text(callback_context: CallbackContext) -> str:
    user_content = callback_context.user_content
    if not user_content or not user_content.parts:
        return ""
    text_parts = [
        part.text.strip()
        for part in user_content.parts
        if getattr(part, "text", None) and part.text.strip()
    ]
    return "\n".join(text_parts).strip()


def extract_response_text(response) -> str:
    if getattr(response, "text", None):
        return response.text.strip()

    for candidate in response.candidates or []:
        if not candidate.content:
            continue
        text_parts = [
            part.text.strip()
            for part in candidate.content.parts or []
            if getattr(part, "text", None) and part.text.strip()
        ]
        if text_parts:
            return "\n".join(text_parts).strip()

    return ""


def summarize_image_generation_response(response) -> str:
    details: list[str] = []
    response_text = extract_response_text(response)
    if response_text:
        details.append(f"text={response_text[:160]!r}")

    for index, candidate in enumerate(response.candidates or [], start=1):
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is not None:
            details.append(f"candidate_{index}_finish_reason={finish_reason}")

        if not candidate.content or not candidate.content.parts:
            details.append(f"candidate_{index}_parts=0")
            continue

        part_summaries = []
        for part in candidate.content.parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                part_summaries.append(f"inline_data:{part.inline_data.mime_type or 'unknown'}")
            elif getattr(part, "text", None):
                part_summaries.append(f"text:{part.text[:80]!r}")
            else:
                part_summaries.append("empty_part")
        details.append(f"candidate_{index}_parts=[{', '.join(part_summaries)}]")

    return "; ".join(details) if details else "no candidates or content returned"


async def generate_storybook_story(callback_context: CallbackContext):
    user_text = extract_user_text(callback_context)
    if not user_text:
        clear_page_asset_refs(callback_context)
        callback_context.state[STORYBOOK_STATE_KEY] = create_empty_storybook_state()
        return build_text_content("이야기 테마를 한 가지 입력해 주세요.")

    try:
        client = Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model=STORY_WRITER_MODEL,
            contents=[user_text],
            config=types.GenerateContentConfig(
                system_instruction=STORY_WRITER_AGENT_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        raw_story_draft = extract_response_text(response)
        writer_response = StoryWriterResponse.model_validate_json(raw_story_draft)
    except Exception as error:
        callback_context.state[STORYBOOK_STATE_KEY] = create_failed_storybook_state(
            callback_context.state.get(STORYBOOK_STATE_KEY),
            f"story_generation_failed: {error}",
            stage="story_writing",
        )
        return build_text_content("스토리 생성에 실패했습니다. 다시 시도해 주세요.")

    if writer_response.status == "needs_theme":
        clear_page_asset_refs(callback_context)
        callback_context.state[STORYBOOK_STATE_KEY] = create_empty_storybook_state()
        return build_text_content(writer_response.message)

    generated_story = create_generated_story_from_writer_response(writer_response)
    clear_page_asset_refs(callback_context)
    callback_context.state[STORYBOOK_STATE_KEY] = (
        create_storybook_state_from_generated_story(generated_story)
    )
    return build_text_content(summarize_story_ready(generated_story.theme))


def build_page_illustration_prompt(storybook_state, page: StoryPageState) -> str:
    return f"""
Create one children's storybook illustration for a single page.

Theme: {storybook_state.theme}
Book length: 5 pages

{build_storybook_style_guide()}

Full storybook overview:
{build_storybook_overview(storybook_state)}

Target page:
- Page number: {page.page_number}
- Story text: {page.page_text}
- Visual description: {page.visual_description}

Requirements:
- Make the image child-friendly, warm, and expressive.
- Match the exact same character designs, environment design, palette, and illustration style used across the whole storybook.
- Treat recurring characters and props as the same individuals from page to page.
- Keep visual continuity with the full storybook overview above.
- Do not include captions, speech bubbles, or printed text inside the image.
- Focus on a clear picture-book composition for this page only.
""".strip()


def build_page_illustration_artifact_basename(theme: str, page_number: int) -> str:
    return f"{slugify_theme(theme)}-illustration-page-{page_number}"


def build_page_storybook_artifact_basename(theme: str, page_number: int) -> str:
    return f"{slugify_theme(theme)}-storybook-page-{page_number}"


def find_existing_artifact(
    existing_artifacts: list[str],
    artifact_basename: str,
) -> str | None:
    artifact_prefix = f"{artifact_basename}."
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

    response_summary = summarize_image_generation_response(response)
    raise ValueError(
        "The image model response did not contain generated image bytes. "
        f"Response summary: {response_summary}"
    )


def generate_page_illustration(
    client: Client,
    storybook_state,
    page: StoryPageState,
    existing_artifacts: list[str],
) -> tuple[str, types.Part | None, tuple[bytes, str] | None]:
    existing_artifact = find_existing_artifact(
        existing_artifacts=existing_artifacts,
        artifact_basename=build_page_illustration_artifact_basename(
            storybook_state.theme,
            page.page_number,
        ),
    )
    if existing_artifact:
        return existing_artifact, None, None

    response = client.models.generate_content(
        model=ILLUSTRATOR_MODEL,
        contents=[build_page_illustration_prompt(storybook_state, page)],
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            seed=build_theme_seed(storybook_state.theme),
            image_config=types.ImageConfig(
                aspect_ratio=ILLUSTRATION_ASPECT_RATIO,
            ),
        ),
    )
    image_bytes, mime_type = extract_generated_image_bytes(response)
    artifact_filename = (
        f"{build_page_illustration_artifact_basename(storybook_state.theme, page.page_number)}"
        f"{mime_type_to_extension(mime_type)}"
    )
    artifact = types.Part(
        inline_data=types.Blob(
            data=image_bytes,
            mime_type=mime_type,
        )
    )
    return artifact_filename, artifact, (image_bytes, mime_type)


def build_storybook_page_asset(
    storybook_state,
    page: StoryPageState,
    illustration_bytes: bytes,
) -> tuple[str, types.Part, tuple[bytes, str]]:
    page_image_bytes, mime_type = compose_storybook_page(
        illustration_bytes=illustration_bytes,
        page_text=page.page_text,
    )
    artifact_filename = (
        f"{build_page_storybook_artifact_basename(storybook_state.theme, page.page_number)}"
        f"{mime_type_to_extension(mime_type)}"
    )
    artifact = types.Part(
        inline_data=types.Blob(
            data=page_image_bytes,
            mime_type=mime_type,
        )
    )
    return artifact_filename, artifact, (page_image_bytes, mime_type)


def format_storybook_result(storybook_state) -> str:
    sections = [f"Title: {format_display_text(storybook_state.title)}"]
    for page in storybook_state.pages:
        sections.append(
            "\n".join(
                [
                    f"Page {page.page_number}:",
                    f"Story Text: {format_display_text(page.page_text)}",
                    "Illustration Artifact: "
                    + (
                        f"[Artifact 저장됨: {page.illustration_ref}]"
                        if page.illustration_ref
                        else "[Artifact 저장되지 않음]"
                    ),
                    "Storybook Page Artifact: "
                    + (
                        f"[Artifact 저장됨: {page.page_image_ref}]"
                        if page.page_image_ref
                        else "[Artifact 저장되지 않음]"
                    ),
                ]
            )
        )
    return "\n\n".join(sections)


def format_storybook_failure(storybook_state) -> str:
    sections = [
        "Storybook generation failed.",
        f"Title: {format_display_text(storybook_state.title)}",
        f"Theme: {format_display_text(storybook_state.theme)}",
        f"Status: {storybook_state.status}",
    ]
    if storybook_state.failed_stage:
        sections.append(f"Failed Stage: {storybook_state.failed_stage}")
    if storybook_state.failed_page_number is not None:
        sections.append(f"Failed Page: {storybook_state.failed_page_number}")
    if storybook_state.error:
        sections.append(f"Error: {format_display_text(storybook_state.error)}")

    page_error_sections = []
    for page in storybook_state.pages:
        if page.error:
            page_error_sections.append(
                "\n".join(
                    [
                        f"Page {page.page_number}:",
                        f"Page Status: {page.status}",
                        f"Page Error: {format_display_text(page.error)}",
                    ]
                )
            )

    if page_error_sections:
        sections.append("")
        sections.extend(page_error_sections)

    return "\n".join(sections)


def find_story_page(storybook_state, page_number: int) -> StoryPageState | None:
    for page in storybook_state.pages:
        if page.page_number == page_number:
            return page
    return None


def format_page_result(page: StoryPageState) -> str:
    return "\n".join(
        [
            f"Page {page.page_number}:",
            f"Text: {format_display_text(page.page_text)}",
            f"Visual: {format_display_text(page.visual_description)}",
            "Image: [생성된 이미지가 Artifact로 저장됨]",
        ]
    )


def build_page_illustration_started_callback(page_number: int):
    def announce_page_illustration_started(callback_context: CallbackContext):
        callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_with_page_status(
            callback_context.state.get(STORYBOOK_STATE_KEY),
            page_number=page_number,
            status="illustration_in_progress",
            error=None,
        )
        return build_text_content(summarize_page_illustration_started(page_number))

    return announce_page_illustration_started


async def load_artifact_bytes(callback_context: CallbackContext, artifact_name: str) -> tuple[bytes, str] | None:
    saved_artifact = await callback_context.load_artifact(artifact_name)
    if (
        saved_artifact
        and saved_artifact.inline_data
        and saved_artifact.inline_data.data
    ):
        return saved_artifact.inline_data.data, saved_artifact.inline_data.mime_type or "image/jpeg"
    return None


async def maybe_skip_illustration_workflow(callback_context: CallbackContext):
    storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))
    if storybook_state.status in {"story_ready", "illustration_in_progress", "illustration_ready"} and len(storybook_state.pages) == 5:
        if storybook_state.status == "story_ready":
            callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_with_status(
                callback_context.state.get(STORYBOOK_STATE_KEY),
                status="illustration_in_progress",
            )
        return None
    return build_empty_content()


async def maybe_skip_storybook_result(callback_context: CallbackContext):
    storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))
    if storybook_state.status == "failed" and storybook_state.error:
        return None
    illustration_refs = extract_page_illustration_refs(callback_context.state, total_pages=5)
    page_image_refs = extract_page_image_refs(callback_context.state, total_pages=5)
    if len(illustration_refs) == 5 and len(page_image_refs) == 5 and len(storybook_state.pages) == 5:
        return None
    return build_empty_content()


def render_storybook_result(callback_context: CallbackContext):
    storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))
    if storybook_state.status == "failed":
        return build_text_content(format_storybook_failure(storybook_state))

    illustration_refs = extract_page_illustration_refs(callback_context.state, total_pages=5)
    page_image_refs = extract_page_image_refs(callback_context.state, total_pages=5)
    callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_from_page_asset_refs(
        callback_context.state.get(STORYBOOK_STATE_KEY),
        illustration_refs=illustration_refs,
        page_image_refs=page_image_refs,
    )
    updated_storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))
    return build_text_content(format_storybook_result(updated_storybook_state))


def build_page_illustration_callback(page_number: int):
    async def generate_single_page_illustration(callback_context: CallbackContext):
        storybook_state = load_storybook_state(callback_context.state.get(STORYBOOK_STATE_KEY))

        if storybook_state.status not in {
            "story_ready",
            "illustration_in_progress",
            "illustration_ready",
        }:
            return build_empty_content()

        page = find_story_page(storybook_state, page_number)
        if page is None:
            return build_empty_content()

        existing_illustration_ref = callback_context.state.get(
            build_page_illustration_ref_state_key(page_number)
        )
        existing_page_image_ref = callback_context.state.get(
            build_page_image_ref_state_key(page_number)
        )
        if (
            isinstance(existing_illustration_ref, str)
            and existing_illustration_ref.strip()
            and isinstance(existing_page_image_ref, str)
            and existing_page_image_ref.strip()
        ):
            illustration_data = await load_artifact_bytes(
                callback_context,
                existing_illustration_ref,
            )
            if illustration_data:
                illustration_bytes, illustration_mime_type = illustration_data
                save_local_image_bytes(
                    theme=storybook_state.theme,
                    page_number=page.page_number,
                    asset_name="illustration",
                    image_bytes=illustration_bytes,
                    mime_type=illustration_mime_type,
                )
            page_image_data = await load_artifact_bytes(
                callback_context,
                existing_page_image_ref,
            )
            if page_image_data:
                page_image_bytes, page_image_mime_type = page_image_data
                save_local_image_bytes(
                    theme=storybook_state.theme,
                    page_number=page.page_number,
                    asset_name="storybook",
                    image_bytes=page_image_bytes,
                    mime_type=page_image_mime_type,
                )
            callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_with_page_status(
                callback_context.state.get(STORYBOOK_STATE_KEY),
                page_number=page_number,
                status="illustration_ready",
                error=None,
            )
            return build_text_content(summarize_page_illustration_completed(page_number))

        try:
            client = Client(api_key=GOOGLE_API_KEY)
            existing_artifacts = await callback_context.list_artifacts()
            illustration_ref = (
                existing_illustration_ref
                if isinstance(existing_illustration_ref, str) and existing_illustration_ref.strip()
                else find_existing_artifact(
                    existing_artifacts,
                    build_page_illustration_artifact_basename(
                        storybook_state.theme,
                        page.page_number,
                    ),
                )
            )
            illustration_data = None
            if illustration_ref:
                illustration_data = await load_artifact_bytes(callback_context, illustration_ref)
                if illustration_data:
                    illustration_bytes, illustration_mime_type = illustration_data
                    save_local_image_bytes(
                        theme=storybook_state.theme,
                        page_number=page.page_number,
                        asset_name="illustration",
                        image_bytes=illustration_bytes,
                        mime_type=illustration_mime_type,
                    )

            if not illustration_data:
                illustration_ref, illustration_artifact, illustration_data = generate_page_illustration(
                    client=client,
                    storybook_state=storybook_state,
                    page=page,
                    existing_artifacts=existing_artifacts,
                )
                if illustration_artifact is not None:
                    await callback_context.save_artifact(
                        filename=illustration_ref,
                        artifact=illustration_artifact,
                    )
                else:
                    illustration_data = await load_artifact_bytes(callback_context, illustration_ref)
                if not illustration_data:
                    raise ValueError("The illustration artifact could not be loaded.")
                illustration_bytes, illustration_mime_type = illustration_data
                save_local_image_bytes(
                    theme=storybook_state.theme,
                    page_number=page.page_number,
                    asset_name="illustration",
                    image_bytes=illustration_bytes,
                    mime_type=illustration_mime_type,
                )

            page_image_ref = (
                existing_page_image_ref
                if isinstance(existing_page_image_ref, str) and existing_page_image_ref.strip()
                else find_existing_artifact(
                    existing_artifacts,
                    build_page_storybook_artifact_basename(
                        storybook_state.theme,
                        page.page_number,
                    ),
                )
            )
            if page_image_ref:
                page_image_data = await load_artifact_bytes(callback_context, page_image_ref)
                if page_image_data:
                    page_image_bytes, page_image_mime_type = page_image_data
                    save_local_image_bytes(
                        theme=storybook_state.theme,
                        page_number=page.page_number,
                        asset_name="storybook",
                        image_bytes=page_image_bytes,
                        mime_type=page_image_mime_type,
                    )
                else:
                    page_image_ref = None

            if not page_image_ref:
                illustration_bytes, _ = illustration_data
                page_image_ref, page_image_artifact, page_image_data = build_storybook_page_asset(
                    storybook_state=storybook_state,
                    page=page,
                    illustration_bytes=illustration_bytes,
                )
                await callback_context.save_artifact(
                    filename=page_image_ref,
                    artifact=page_image_artifact,
                )
                page_image_bytes, page_image_mime_type = page_image_data
                save_local_image_bytes(
                    theme=storybook_state.theme,
                    page_number=page.page_number,
                    asset_name="storybook",
                    image_bytes=page_image_bytes,
                    mime_type=page_image_mime_type,
                )
        except Exception as error:
            callback_context.state[STORYBOOK_STATE_KEY] = create_failed_storybook_state(
                callback_context.state.get(STORYBOOK_STATE_KEY),
                f"illustration_generation_failed: {error}",
                stage="illustration",
                page_number=page_number,
            )
            return build_text_content(
                f"이미지 {page_number}/5 생성에 실패했습니다. 다시 시도해 주세요."
            )

        callback_context.state[build_page_illustration_ref_state_key(page_number)] = illustration_ref
        callback_context.state[build_page_image_ref_state_key(page_number)] = page_image_ref
        callback_context.state[STORYBOOK_STATE_KEY] = create_storybook_state_with_page_status(
            callback_context.state.get(STORYBOOK_STATE_KEY),
            page_number=page_number,
            status="illustration_ready",
            error=None,
        )
        return build_text_content(summarize_page_illustration_completed(page_number))

    return generate_single_page_illustration


story_writer_progress_agent = Agent(
    name="StoryWriterProgressAgent",
    model=STORY_WRITER_MODEL,
    description="Announces the start of story generation.",
    instruction="Announce that the story writing step is starting.",
    before_agent_callback=announce_story_writing_started,
)

story_writer_worker_agent = Agent(
    name="StoryWriterWorkerAgent",
    model=STORY_WRITER_MODEL,
    description=STORY_WRITER_AGENT_DESCRIPTION,
    instruction=STORY_WRITER_AGENT_INSTRUCTION,
    before_agent_callback=ensure_storybook_state,
    after_agent_callback=None,
)

story_writer_worker_agent.before_agent_callback = [
    ensure_storybook_state,
    generate_storybook_story,
]

story_writer_agent = SequentialAgent(
    name="StoryWriterAgent",
    description="Shows story writing progress and stores the generated story in shared state.",
    sub_agents=[story_writer_progress_agent, story_writer_worker_agent],
)

page_illustration_workflows = [
    SequentialAgent(
        name=f"IllustratorPage{page_number}Workflow",
        description=f"Announces, generates, and completes the illustration for page {page_number}.",
        sub_agents=[
            Agent(
                name=f"IllustratorPage{page_number}StartAgent",
                model=ILLUSTRATOR_MODEL,
                description=f"Announces the start of page {page_number} illustration generation.",
                instruction=f"Announce the start of page {page_number} illustration generation.",
                before_agent_callback=build_page_illustration_started_callback(page_number),
            ),
            Agent(
                name=f"IllustratorPage{page_number}Agent",
                model=ILLUSTRATOR_MODEL,
                description=f"Generates and reports the illustration for page {page_number}.",
                instruction=ILLUSTRATOR_AGENT_INSTRUCTION,
                before_agent_callback=build_page_illustration_callback(page_number),
            ),
        ],
    )
    for page_number in range(1, 6)
]

illustration_workflow_agent = ParallelAgent(
    name="IllustrationWorkflow",
    description="Runs the five page illustration agents in parallel.",
    before_agent_callback=maybe_skip_illustration_workflow,
    sub_agents=page_illustration_workflows,
)

illustrator_agent = illustration_workflow_agent

storybook_result_agent = Agent(
    name="StorybookResultAgent",
    model=STORY_WRITER_MODEL,
    description="Formats the completed storybook output after illustration finishes.",
    instruction="Render the completed storybook result.",
    before_agent_callback=[ensure_storybook_state, maybe_skip_storybook_result, render_storybook_result],
)

root_agent = SequentialAgent(
    name="StoryBookWorkflow",
    description="Runs story writing, illustration, and final result rendering in order.",
    sub_agents=[story_writer_agent, illustration_workflow_agent, storybook_result_agent],
)
