# tests/unit/test_ai_engine/test_llm_config.py

"""Unit tests for ai_engine.llm_config — LLM provider registry.

Tests the AGENT_LLM_REGISTRY mapping to ensure every agent role is
assigned to the correct provider, model, temperature, and token cap.
No API calls are made — these are pure config-validation tests.
"""

import pytest

from ai_engine.llm import AGENT_LLM_REGISTRY, Provider


class TestAgentRegistry:
    """Verify every entry in AGENT_LLM_REGISTRY has the expected config."""

    def test_router_config(self):
        """router → Groq Llama 3.3 70B, low temp for consistent extraction."""
        config = AGENT_LLM_REGISTRY["router"]
        assert config.provider == Provider.GROQ
        assert config.model == "llama-3.3-70b-versatile"
        assert config.temperature == 0.2
        assert config.max_tokens == 2048

    def test_preference_reranker_config(self):
        """preference_reranker → Groq Llama 3.3 70B, low temp for consistent reranking."""
        config = AGENT_LLM_REGISTRY["preference_reranker"]
        assert config.provider == Provider.GROQ
        assert config.model == "llama-3.3-70b-versatile"
        assert config.temperature == 0.2
        assert config.max_tokens == 2048

    def test_validator_config(self):
        """validator → Groq Llama 3.3 70B, low temp for consistent checks."""
        config = AGENT_LLM_REGISTRY["validator"]
        assert config.provider == Provider.GROQ
        assert config.model == "llama-3.3-70b-versatile"
        assert config.temperature == 0.2
        assert config.max_tokens == 2048

    def test_review_qa_config(self):
        """review_qa → Groq Llama 3.3 70B, higher temp for natural QA."""
        config = AGENT_LLM_REGISTRY["review_qa"]
        assert config.provider == Provider.GROQ
        assert config.model == "llama-3.3-70b-versatile"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192

    def test_modifier_config(self):
        """modifier → Gemini 2.5 Flash, temperature 0 for deterministic edits."""
        config = AGENT_LLM_REGISTRY["modifier"]
        assert config.provider == Provider.GEMINI
        assert config.model == "gemini-2.5-flash"
        assert config.temperature == 0.0
        assert config.max_tokens == 8192

    def test_planner_config(self):
        """planner → Gemini 2.5 Flash, moderate temp for creative itineraries."""
        config = AGENT_LLM_REGISTRY["planner"]
        assert config.provider == Provider.GEMINI
        assert config.model == "gemini-2.5-flash"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192

    def test_vision_config(self):
        """vision → Gemini 2.5 Flash (multimodal), moderate temp."""
        config = AGENT_LLM_REGISTRY["vision"]
        assert config.provider == Provider.GEMINI
        assert config.model == "gemini-2.5-flash"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192

    def test_all_roles_have_config(self):
        """Every registered agent role has a valid config with required fields."""
        for role, config in AGENT_LLM_REGISTRY.items():
            assert config.provider in (Provider.GEMINI, Provider.GROQ), (
                f"{role}: unknown provider {config.provider}"
            )
            assert isinstance(config.model, str) and len(config.model) > 0, (
                f"{role}: missing model name"
            )
            assert 0.0 <= config.temperature <= 2.0, (
                f"{role}: temperature {config.temperature} out of range"
            )
            assert config.max_tokens > 0, (
                f"{role}: max_tokens must be positive"
            )

    def test_known_role_count(self):
        """The registry should have exactly 10 agent roles."""
        assert len(AGENT_LLM_REGISTRY) == 10, (
            f"Expected 10 agent roles, got {len(AGENT_LLM_REGISTRY)}. "
            "If you added a new agent, update this test."
        )

    def test_unknown_role_raises_key_error(self):
        """Accessing an unregistered role raises KeyError."""
        with pytest.raises(KeyError):
            _ = AGENT_LLM_REGISTRY["nonexistent_agent"]

    def test_groq_agents_use_groq_provider(self):
        """All three Groq agents share the same provider."""
        groq_roles = ["router", "preference_reranker", "validator", "review_qa"]
        for role in groq_roles:
            assert AGENT_LLM_REGISTRY[role].provider == Provider.GROQ, (
                f"{role} should use Groq"
            )

    def test_gemini_agents_use_gemini_provider(self):
        """All three Gemini agents share the same provider."""
        gemini_roles = ["modifier", "planner", "vision"]
        for role in gemini_roles:
            assert AGENT_LLM_REGISTRY[role].provider == Provider.GEMINI, (
                f"{role} should use Gemini"
            )

    def test_modifier_placed_under_gemini_section(self):
        """The modifier entry appears after the '# ── Gemini' comment in source,
        verifying it's grouped under the Gemini section (not Groq)."""
        # The AGENT_LLM_REGISTRY lives in ai_engine/llm/config.py
        import ai_engine.llm.config as llm_config_module

        with open(llm_config_module.__file__, encoding="utf-8") as f:
            source = f.read()

        groq_section_end = source.find("# ── Gemini")
        modifier_pos = source.find('"modifier"')
        assert groq_section_end < modifier_pos, (
            "modifier should be registered AFTER the Groq section and "
            "under the '# ── Gemini' comment"
        )
