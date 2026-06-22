"""
Shared JSON extraction and repair utilities for LLM outputs.

LLMs often produce JSON with common issues:
1. Preamble text before the JSON object
2. Markdown code fences (```json ... ```)
3. Trailing commentary after JSON
4. Missing commas between fields (Gemini-common)
5. Truncated JSON (unterminated strings, unclosed brackets)

These helpers extract and repair JSON from LLM responses so that
downstream agents can reliably parse the output.
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def extract_json_from_llm_output(text: str) -> str:
    """Extract a JSON object from LLM output that may contain preamble,
    markdown fences, or trailing commentary.

    Fixes three common LLM output issues:
    1. Preamble text before JSON ("Here is your itinerary: { ... }")
    2. Markdown code fences (```json ... ```)
    3. Trailing commentary after JSON

    Returns the extracted JSON string (still needs json.loads to parse).

    Raises:
        ValueError: If no JSON object can be found in the text.
    """
    if not text:
        raise ValueError("Empty LLM output")

    # Step 1: Remove markdown code fences if present.
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Step 2: If it already looks like valid JSON, return as-is.
    if text.startswith("{") and text.endswith("}"):
        return text

    # Step 3: Find the first '{' and last '}' to extract the JSON object.
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        raise ValueError(
            f"No JSON object found in LLM output (first 200 chars: {text[:200]!r})"
        )

    return text[first_brace:last_brace + 1]


def repair_missing_commas(text: str) -> str:
    """Insert missing commas by using json.JSONDecodeError position hints.

    The LLM (especially Gemini) commonly produces JSON with missing commas
    between fields, like:
        {"name": "Museum" "id": "123"}   → missing comma after "Museum"
        {"scores": [1 2 3]}               → missing commas in array
        {"a": 1 {"b": 2}}               → missing comma before nested object

    This function iteratively:
    1. Attempts json.loads()
    2. If it fails with a missing-comma error, inserts a comma at the
       error position and retries (up to 5 iterations).

    Returns the repaired JSON string (which may still be invalid on
    non-comma errors — the caller falls through to repair_truncated_json).
    """
    repaired = text

    for _ in range(5):
        try:
            json.loads(repaired)
            return repaired  # Valid JSON — done
        except json.JSONDecodeError as e:
            # Only handle missing comma / property name errors here.
            if not ("Expecting '" in e.msg and "delimiter" in e.msg):
                if "Expecting property name" not in e.msg:
                    break  # Non-comma error — let truncation repair handle it
            pos = e.pos
            # Guard: don't insert at end of string
            if pos >= len(repaired):
                break
            if repaired[pos] in (',', '}', ']', ':', ' '):
                break  # Already has comma or structural — different issue

            # If error position points to a key inside a newly-started nested
            # object (e.g. {"a": 1 {"b": 2}}), the comma needs to go BEFORE
            # the opening brace, not before the key string.
            if (pos > 0 and repaired[pos] == '"'
                    and repaired[pos - 1] in ('{', '[')):
                pos = pos - 1

            repaired = repaired[:pos] + ',' + repaired[pos:]
            continue

    return repaired  # Best attempt


def repair_truncated_json(text: str) -> str:
    """Attempt to repair JSON that was truncated by max_tokens limit.

    Common truncation patterns:
    - Unterminated string: '"name": "Some place' → close the string
    - Missing closing brackets: incomplete days/stops arrays

    Returns the repaired JSON string.
    """
    repaired = text.rstrip()

    # If it's already valid, return as-is.
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        pass

    # Strategy 1: Close an unterminated string at the end.
    # If the last non-whitespace char is not a quote, bracket, or comma,
    # we're likely mid-string or mid-value.
    if repaired and repaired[-1] not in ('"', '}', ']', ',', ':', ' '):
        # Check if we're inside a string (odd number of unescaped quotes)
        in_string = False
        for ch in reversed(repaired):
            if ch == '"':
                in_string = not in_string
        if in_string:
            repaired += '"'

    # Strategy 2: Count unmatched opening brackets and close them.
    open_braces = 0
    open_brackets = 0
    in_str = False
    escape_next = False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1

    # Close any unclosed brackets/braces (innermost first)
    closing = ']' * max(open_brackets, 0) + '}' * max(open_braces, 0)
    repaired += closing

    # Validate the repair.
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        # Could not repair — return the best attempt.
        return repaired
