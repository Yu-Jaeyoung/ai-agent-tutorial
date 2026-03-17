from google.adk.agents import Agent

from prompt import STORY_BOOK_AGENT_DESCRIPTION, STORY_BOOK_AGENT_INSTRUCTION

story_book_agent = Agent(
    name="StoryBookAgent",
    description=STORY_BOOK_AGENT_DESCRIPTION,
    instruction=STORY_BOOK_AGENT_INSTRUCTION,
)
