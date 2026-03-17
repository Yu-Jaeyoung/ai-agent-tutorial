import os

import dotenv

dotenv.load_dotenv()


if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError("GOOGLE_API_KEY must be set in the project .env file.")


STORY_WRITER_MODEL = os.getenv(
    "STORY_WRITER_MODEL",
    os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
)

ILLUSTRATOR_MODEL = os.getenv(
    "ILLUSTRATOR_MODEL",
    os.getenv("GOOGLE_IMAGE_MODEL", "gemini-2.5-flash-image"),
)
