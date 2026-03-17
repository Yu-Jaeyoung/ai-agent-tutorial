from google.adk.agents import Agent

from .prompt import STORY_WRITER_AGENT_DESCRIPTION, STORY_WRITER_AGENT_INSTRUCTION
from .settings import STORY_WRITER_MODEL


story_writer_agent = Agent(
    name="StoryWriterAgent",
    model=STORY_WRITER_MODEL,
    description=STORY_WRITER_AGENT_DESCRIPTION,
    instruction=STORY_WRITER_AGENT_INSTRUCTION,
)

root_agent = story_writer_agent
