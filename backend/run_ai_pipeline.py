
import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from ai_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# Mocking app.external.groq_client and other dependencies if necessary
# But we already created groq_client.py in the correct place.

from ai_engine.chat.chat_handler import handle_chat

async def main():
    print("Starting AI Pipeline Test...")
    
    user_id = "test_user_123"
    user_message = "Plan me a 2-day trip to Cairo focusing on history and food."
    
    print(f"User Message: {user_message}")
    
    try:
        result = await handle_chat(user_id=user_id, user_message=user_message)
        
        print("\n--- Test Result ---")
        print(f"Response Type: {result.get('response_type')}")
        print(f"Message: {result.get('message')}")
        
        # Check for pipeline errors
        if result.get("error"):
            print(f"Pipeline Error: {result.get('error')}")
        
        itinerary = result.get("itinerary")
        if itinerary:
            print("\nGenerated Itinerary:")
            import json
            print(json.dumps(itinerary, indent=2))
        else:
            print("\nNo itinerary generated.")
            
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Check for GOOGLE_API_KEY in OS env first, then fall back to .env via pydantic-settings
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            from app.core.config import settings
            api_key = settings.google_api_key
        except Exception:
            # Settings() may fail if other required .env vars are missing
            api_key = None

    if not api_key:
        print("Warning: GOOGLE_API_KEY not found in environment or .env file.")
        print("Set GOOGLE_API_KEY in your .env file or as an environment variable.")
    else:
        print(f"GOOGLE_API_KEY loaded from {'env var' if os.environ.get('GOOGLE_API_KEY') else '.env file'}.")
    
    asyncio.run(main())
