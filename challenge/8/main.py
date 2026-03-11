import dotenv
from openai import OpenAI

dotenv.load_dotenv()
client = OpenAI()

# Triage Agent: Determines what the customer needs
# Menu Agent: Answers questions about the menu, ingredients, allergies
# Order Agent: Takes and confirms orders
# Reservation Agent: Handles table bookings
# Complaints Agent: Handle dissatisfied customers with care and provide effective
# Input Guardrails: Filter out inappropriate or off-topic messages from users.
# Output Guardrails: Ensure the bot does not generate inappropriate or non-compliant responses.
