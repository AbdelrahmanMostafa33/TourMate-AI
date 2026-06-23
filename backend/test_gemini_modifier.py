"""
Quick test: Verify the modifier config was updated to use Gemini.
This doesn't call any LLM — just checks that the config is correct.
"""
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
from dotenv import load_dotenv
load_dotenv()

from ai_engine.llm_config import AGENT_LLM_REGISTRY, Provider

# Check the modifier config
config = AGENT_LLM_REGISTRY.get("modifier")
assert config is not None, "modifier not found in registry!"
assert config.provider == Provider.GEMINI, f"Expected GEMINI, got {config.provider}"
assert config.model == "gemini-2.5-flash", f"Expected gemini-2.5-flash, got {config.model}"
assert config.temperature == 0.5, f"Expected 0.5, got {config.temperature}"
assert config.max_tokens == 8192, f"Expected 8192, got {config.max_tokens}"

print("✅ modifier config is correct:")
print(f"   Provider: {config.provider.value}")
print(f"   Model:    {config.model}")
print(f"   Temp:     {config.temperature}")
print(f"   MaxTok:   {config.max_tokens}")
print()

# Verify it's in the Gemini section (after Groq section)
registry_lines = open("ai_engine/llm_config.py", "r", encoding="utf-8").read()
groq_section_end = registry_lines.find("# ── Gemini")
modifier_pos = registry_lines.find('"modifier"')

assert groq_section_end < modifier_pos, "modifier should be AFTER the Groq section"

print("✅ modifier is correctly placed under the Gemini section")
print()
print("--- All checks passed ---")
