import os

from google.adk.agents import Agent

from .prompt import STORY_WRITER_AGENT_DESCRIPTION, STORY_WRITER_AGENT_INSTRUCTION


DEFAULT_STORY_WRITER_MODEL = os.getenv(
    "STORY_WRITER_MODEL",
    os.getenv("GOOGLE_GENAI_MODEL", ""),
)


story_writer_agent = Agent(
    name="StoryWriterAgent",
    model=DEFAULT_STORY_WRITER_MODEL,
    description=STORY_WRITER_AGENT_DESCRIPTION,
    instruction=STORY_WRITER_AGENT_INSTRUCTION,
)

root_agent = story_writer_agent
