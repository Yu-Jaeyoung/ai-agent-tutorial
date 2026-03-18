from pathlib import Path
import os

import dotenv

dotenv.load_dotenv()


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY must be set in the project .env file.")


STORY_WRITER_MODEL = os.getenv(
    "STORY_WRITER_MODEL",
    os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
)

ILLUSTRATOR_MODEL = os.getenv(
    "ILLUSTRATOR_MODEL",
    os.getenv("GOOGLE_IMAGE_MODEL", "gemini-2.5-flash-image"),
)

ILLUSTRATION_ASPECT_RATIO = os.getenv(
    "ILLUSTRATION_ASPECT_RATIO",
    "4:3",
)

GENERATED_IMAGES_DIR = Path(__file__).resolve().parent / "generated"
