# Challenge 10 Verification

## Run

From the repository root:

```bash
uv run adk web challenge/10
```

Open the ADK Web UI and select `story_book_maker`.

## Suggested Inputs

- `용감한 아기 고양이 이야기`
- `우정`

## What To Verify

- The workflow root loads as `StoryBookWorkflow`.
- The writer stage shows progress messages instead of raw JSON output.
- The writer stage produces a title and exactly 5 story pages in shared state.
- The illustration stage runs as a parallel workflow with 5 page branches.
- The UI shows page illustration progress events such as `이미지 1/5 생성 중...` and `이미지 1/5 생성 완료`.
- Page progress messages may appear in completion order rather than page-number order.
- Each page stores both a raw illustration Artifact and a final storybook page Artifact.
- Each generated page is also mirrored under `challenge/10/story_book_maker/generated/<theme-slug>/`.
- The local generated directory contains both:
  - `illustration_page_1.*`
  - `storybook_page_1.*`
- The final response renders the complete storybook with:
  - `Title`
  - `Page 1` to `Page 5`
  - `Story Text`
  - `Illustration Artifact`
  - `Storybook Page Artifact`
- The final `storybook.status` is `illustration_ready`.
- The final page Artifact should already contain the rendered Korean story text inside the image.

## Failure Checks

- Empty or invalid user input asks for one story theme and does not start illustration.
- Story generation failures set `storybook.status` to `failed`.
- Illustration failures set `storybook.status` to `failed` and keep an error message in state.
