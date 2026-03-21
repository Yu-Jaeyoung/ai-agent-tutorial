import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STORYBOOK_PAGE_MIME_TYPE = "image/png"
TEXT_PANEL_RATIO = 0.35
TEXT_PANEL_MIN_HEIGHT = 220
TEXT_PANEL_BACKGROUND = (250, 247, 239, 255)
TEXT_PANEL_BORDER = (222, 214, 198, 255)
TEXT_COLOR = (32, 32, 32, 255)
TEXT_PADDING_RATIO = 0.06
TEXT_MIN_FONT_SIZE = 24
TEXT_MAX_FONT_SIZE = 60
TEXT_MAX_LINES = 4
TEXT_LINE_SPACING = 10
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/HelveticaNeue.ttc"),
]


def resolve_storybook_font_path() -> Path:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            return font_path
    raise RuntimeError("No usable system font was found for storybook page composition.")


def normalize_story_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    normalized_text = normalize_story_text(text)
    if not normalized_text:
        return [""]

    lines: list[str] = []
    current = ""
    for char in normalized_text:
        candidate = f"{current}{char}"
        candidate_width, _ = measure_text(draw, candidate, font)
        if current and candidate_width > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
        else:
            current = candidate

    if current:
        lines.append(current.rstrip())
    return lines or [normalized_text]


def truncate_lines_to_fit(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if len(lines) <= max_lines:
        return lines

    truncated = lines[:max_lines]
    last_line = truncated[-1].rstrip()
    ellipsis = "..."
    while last_line:
        candidate = f"{last_line}{ellipsis}"
        candidate_width, _ = measure_text(draw, candidate, font)
        if candidate_width <= max_width:
            truncated[-1] = candidate
            break
        last_line = last_line[:-1].rstrip()
    else:
        truncated[-1] = ellipsis
    return truncated


def fit_text_layout(
    text: str,
    panel_width: int,
    panel_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    measurement_image = Image.new("RGBA", (panel_width, panel_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(measurement_image)
    font_path = resolve_storybook_font_path()

    for font_size in range(TEXT_MAX_FONT_SIZE, TEXT_MIN_FONT_SIZE - 1, -2):
        font = ImageFont.truetype(str(font_path), font_size)
        lines = wrap_text_to_width(draw, text, font, panel_width)
        line_height = measure_text(draw, "가Ag", font)[1]
        total_height = len(lines) * line_height + max(0, len(lines) - 1) * TEXT_LINE_SPACING
        if len(lines) <= TEXT_MAX_LINES and total_height <= panel_height:
            return font, lines, line_height

    font = ImageFont.truetype(str(font_path), TEXT_MIN_FONT_SIZE)
    lines = wrap_text_to_width(draw, text, font, panel_width)
    lines = truncate_lines_to_fit(draw, lines, font, panel_width, TEXT_MAX_LINES)
    line_height = measure_text(draw, "가Ag", font)[1]
    return font, lines, line_height


def compose_storybook_page(
    illustration_bytes: bytes,
    page_text: str,
) -> tuple[bytes, str]:
    illustration = Image.open(io.BytesIO(illustration_bytes)).convert("RGBA")
    width, height = illustration.size

    panel_height = max(int(height * TEXT_PANEL_RATIO), TEXT_PANEL_MIN_HEIGHT)
    page_height = height + panel_height
    page_image = Image.new("RGBA", (width, page_height), (255, 255, 255, 255))
    page_image.paste(illustration, (0, 0))

    draw = ImageDraw.Draw(page_image)
    panel_top = height
    draw.rectangle(
        [(0, panel_top), (width, page_height)],
        fill=TEXT_PANEL_BACKGROUND,
    )
    draw.line([(0, panel_top), (width, panel_top)], fill=TEXT_PANEL_BORDER, width=2)

    padding_x = max(int(width * TEXT_PADDING_RATIO), 24)
    padding_y = max(int(panel_height * 0.16), 24)
    available_width = width - (padding_x * 2)
    available_height = panel_height - (padding_y * 2)

    font, lines, line_height = fit_text_layout(
        text=page_text,
        panel_width=available_width,
        panel_height=available_height,
    )

    total_text_height = len(lines) * line_height + max(0, len(lines) - 1) * TEXT_LINE_SPACING
    text_y = panel_top + padding_y + max((available_height - total_text_height) // 2, 0)

    for line in lines:
        draw.text(
            (padding_x, text_y),
            line,
            font=font,
            fill=TEXT_COLOR,
        )
        text_y += line_height + TEXT_LINE_SPACING

    output = io.BytesIO()
    page_image.convert("RGB").save(output, format="PNG")
    return output.getvalue(), STORYBOOK_PAGE_MIME_TYPE
