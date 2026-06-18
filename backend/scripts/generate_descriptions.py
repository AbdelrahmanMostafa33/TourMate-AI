"""
Generate missing descriptions for dubai_places_class_diagram.json using Gemini API.
Processes entries in batches for efficiency.
"""
import json
import time
import os
import google.generativeai as genai
from collections import Counter

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyCplaceholder")
if GOOGLE_API_KEY.startswith("AQ."):
    # Read from .env file if not in environment
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("GOOGLE_API_KEY="):
                    GOOGLE_API_KEY = line.strip().split("=", 1)[1]
                    break

genai.configure(api_key=GOOGLE_API_KEY)

BATCH_SIZE = 10  # places per API call
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dubai", "dubai_places_class_diagram.json")


def build_prompt_for_batch(places_batch):
    """Build a prompt that asks Gemini to generate descriptions for a batch of places."""
    lines = []
    for i, p in enumerate(places_batch):
        line = f"[{i+1}] name={p['name']}, category={p.get('category','')}"
        if p.get("address"):
            line += f", address={p['address']}"
        if p.get("rating"):
            line += f", rating={p['rating']}"
        if p.get("reviewCount"):
            line += f", reviews={p['reviewCount']}"
        if p.get("phone"):
            line += f", phone={p['phone']}"
        if p.get("website"):
            line += f", website={p['website']}"
        # Include attraction tags if available
        details = p.get("attractionDetails") or {}
        if details.get("tags"):
            line += f", tags={details['tags']}"
        if details.get("subcategory"):
            line += f", subcategory={details['subcategory']}"
        lines.append(line)

    places_text = "\n".join(lines)

    prompt = f"""You are a travel guide writer. Generate concise, engaging descriptions for places in Dubai, UAE.
Each description should be 2-4 sentences, mentioning what the place is, its location in Dubai, and what visitors can expect. Be factual and informative.

Here are the places:
{places_text}

Return ONLY a JSON array of descriptions in the same order, with no additional text. Each description should be a string.
Example output: ["Description 1.", "Description 2."]
"""
    return prompt


def parse_descriptions_from_response(response_text):
    """Extract the JSON array of descriptions from the Gemini response."""
    # Find JSON array in response
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        json_str = text[start:end+1]
        try:
            descriptions = json.loads(json_str)
            if isinstance(descriptions, list):
                return descriptions
        except json.JSONDecodeError:
            pass
    return None


def main():
    print(f"Loading data from {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Total entries: {len(data)}")

    # Find entries missing descriptions
    missing_indices = [i for i, p in enumerate(data) if not p.get("description")]
    print(f"Entries missing description: {len(missing_indices)}")

    if not missing_indices:
        print("All entries already have descriptions. Nothing to do.")
        return

    # Initialize model
    model = genai.GenerativeModel("gemini-2.0-flash")

    filled = 0
    failed = 0
    total_batches = (len(missing_indices) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(0, len(missing_indices), BATCH_SIZE):
        batch_indices = missing_indices[batch_num:batch_num + BATCH_SIZE]
        batch_places = [data[i] for i in batch_indices]
        batch_num_actual = batch_num // BATCH_SIZE + 1

        print(f"\n--- Batch {batch_num_actual}/{total_batches} ({len(batch_places)} places) ---")

        prompt = build_prompt_for_batch(batch_places)

        try:
            response = model.generate_content(prompt)
            descriptions = parse_descriptions_from_response(response.text)

            if descriptions and len(descriptions) == len(batch_places):
                for idx, desc in zip(batch_indices, descriptions):
                    data[idx]["description"] = desc.strip()
                    filled += 1
                print(f"  Filled {len(batch_places)} descriptions successfully.")
            else:
                print(f"  WARN: Expected {len(batch_places)} descriptions, got {len(descriptions) if descriptions else 0}. Skipping batch.")
                failed += len(batch_places)
                # Print response for debugging
                print(f"  Response: {response.text[:300]}")

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += len(batch_places)

        # Rate limiting - small delay between batches
        if batch_num + BATCH_SIZE < len(missing_indices):
            time.sleep(1)

    print(f"\n=== Summary ===")
    print(f"Filled: {filled}")
    print(f"Failed: {failed}")
    print(f"Remaining without description: {sum(1 for p in data if not p.get('description'))}")

    # Save
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nFile saved to {DATA_PATH}")


if __name__ == "__main__":
    main()
