# Import sys and Path to manipulate Python paths
import sys
from pathlib import Path

# Add the parent directory to Python path so imports work no matter where you run this script from
# This allows 'services' and other modules to be imported correctly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import HumanMessage, a wrapper for human input for the model
from langchain_core.messages import HumanMessage

# Import the function that gives a configured Gemini LLM instance
from services.gemini_client import get_gemini_llm


# Function to test if the Gemini model is working
def test_gemini_connection():
    # Get a ready-to-use Gemini LLM object
    llm = get_gemini_llm()

    # Create a list of messages to send to the model
    messages = [
        HumanMessage(content="Suggest one tourist activity in Cairo in one sentence.")
    ]

    print("Sending request to Gemini...")

    # Send messages to the model and get the response
    response = llm.invoke(messages)

    # Print the model's response
    print(f"\n✅ Gemini responded:\n{response.content}")

    # Simple checks to make sure the response is valid (not empty or None)
    assert response.content is not None
    assert len(response.content) > 0


# Run the test if this script is executed directly
if __name__ == "__main__":
    test_gemini_connection()