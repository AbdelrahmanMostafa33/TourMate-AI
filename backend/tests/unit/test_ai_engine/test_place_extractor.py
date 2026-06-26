"""
Unit tests for Place Name Extractor and Hybrid Search functionality.

Tests the place name extraction LLM and the hybrid search pipeline
that combines exact matching with vector search.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai_engine.services.place_extractor import (
    extract_place_name,
    is_high_confidence_extraction,
    is_add_action,
    is_remove_action,
    PlaceNameExtraction,
)


class TestPlaceNameExtraction:
    """Test place name extraction from modification requests."""

    @pytest.mark.asyncio
    async def test_extract_specific_place_name(self):
        """Test extraction of a specific place name."""
        modification_request = "Add the Grand Egyptian Museum to my trip"
        
        with patch('ai_engine.services.place_extractor.invoke_with_fallback') as mock_invoke:
            mock_invoke.return_value = PlaceNameExtraction(
                place_name="Grand Egyptian Museum",
                confidence=1.0,
                action="add"
            )
            
            result = await extract_place_name(modification_request)
            
            assert result.place_name == "Grand Egyptian Museum"
            assert result.confidence == 1.0
            assert result.action == "add"

    @pytest.mark.asyncio
    async def test_extract_vague_request(self):
        """Test extraction returns low confidence for vague requests."""
        modification_request = "Add a nice restaurant"
        
        with patch('ai_engine.services.place_extractor.invoke_with_fallback') as mock_invoke:
            mock_invoke.return_value = PlaceNameExtraction(
                place_name=None,
                confidence=0.0,
                action="add"
            )
            
            result = await extract_place_name(modification_request)
            
            assert result.place_name is None
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_extract_remove_request(self):
        """Test extraction identifies remove actions."""
        modification_request = "Remove the Pyramids of Giza"
        
        with patch('ai_engine.services.place_extractor.invoke_with_fallback') as mock_invoke:
            mock_invoke.return_value = PlaceNameExtraction(
                place_name="Pyramids of Giza",
                confidence=0.9,
                action="remove"
            )
            
            result = await extract_place_name(modification_request)
            
            assert result.place_name == "Pyramids of Giza"
            assert result.action == "remove"

    @pytest.mark.asyncio
    async def test_extract_empty_request(self):
        """Test extraction handles empty requests."""
        result = await extract_place_name("")
        
        assert result.place_name is None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_extract_llm_failure(self):
        """Test extraction handles LLM failures gracefully."""
        modification_request = "Add the Grand Egyptian Museum"
        
        with patch('ai_engine.services.place_extractor.invoke_with_fallback') as mock_invoke:
            mock_invoke.side_effect = Exception("LLM error")
            
            result = await extract_place_name(modification_request)
            
            assert result.place_name is None
            assert result.confidence == 0.0


class TestExtractionHelpers:
    """Test helper functions for extraction results."""

    def test_is_high_confidence_true(self):
        """Test high confidence detection."""
        extraction = PlaceNameExtraction(
            place_name="Grand Egyptian Museum",
            confidence=0.8,
            action="add"
        )
        assert is_high_confidence_extraction(extraction) is True

    def test_is_high_confidence_false(self):
        """Test low confidence detection."""
        extraction = PlaceNameExtraction(
            place_name="Grand Egyptian Museum",
            confidence=0.5,
            action="add"
        )
        assert is_high_confidence_extraction(extraction) is False

    def test_is_high_confidence_none(self):
        """Test None place name returns false."""
        extraction = PlaceNameExtraction(
            place_name=None,
            confidence=1.0,
            action="add"
        )
        assert is_high_confidence_extraction(extraction) is False

    def test_is_add_action_true(self):
        """Test add action detection."""
        extraction = PlaceNameExtraction(
            place_name="Grand Egyptian Museum",
            confidence=1.0,
            action="add"
        )
        assert is_add_action(extraction) is True

    def test_is_add_action_variations(self):
        """Test add action variations."""
        for action in ["add", "ADD", "Add", "include", "INSERT"]:
            extraction = PlaceNameExtraction(
                place_name="Test",
                confidence=1.0,
                action=action
            )
            assert is_add_action(extraction) is True

    def test_is_add_action_false(self):
        """Test non-add actions return false."""
        extraction = PlaceNameExtraction(
            place_name="Grand Egyptian Museum",
            confidence=1.0,
            action="remove"
        )
        assert is_add_action(extraction) is False

    def test_is_remove_action_true(self):
        """Test remove action detection."""
        extraction = PlaceNameExtraction(
            place_name="Pyramids",
            confidence=1.0,
            action="remove"
        )
        assert is_remove_action(extraction) is True

    def test_is_remove_action_variations(self):
        """Test remove action variations."""
        for action in ["remove", "REMOVE", "delete", "exclude"]:
            extraction = PlaceNameExtraction(
                place_name="Test",
                confidence=1.0,
                action=action
            )
            assert is_remove_action(extraction) is True


class TestHybridSearch:
    """Test hybrid search functionality in pool_manager."""

    @pytest.mark.asyncio
    async def test_hybrid_search_exact_match(self):
        """Test hybrid search finds exact match in pool."""
        from ai_engine.services.pool_manager import find_place_for_add
        
        available_places = [
            {"id": "gem_001", "name": "Grand Egyptian Museum", "city": "Giza", "country": "Egypt"},
            {"id": "pyr_001", "name": "Pyramids of Giza", "city": "Giza", "country": "Egypt"},
        ]
        
        with patch('ai_engine.services.pool_manager.extract_place_name') as mock_extract:
            mock_extract.return_value = PlaceNameExtraction(
                place_name="Grand Egyptian Museum",
                confidence=1.0,
                action="add"
            )
            
            result = await find_place_for_add(
                modification_request="Add the Grand Egyptian Museum",
                city="Giza",
                country="Egypt",
                available_places=available_places,
                preferences=None
            )
            
            assert result is not None
            assert result["id"] == "gem_001"
            assert result["name"] == "Grand Egyptian Museum"

    @pytest.mark.asyncio
    async def test_hybrid_search_low_confidence_fallback(self):
        """Test hybrid search returns None for low confidence extractions."""
        from ai_engine.services.pool_manager import find_place_for_add
        
        available_places = [
            {"id": "gem_001", "name": "Grand Egyptian Museum", "city": "Giza", "country": "Egypt"},
        ]
        
        with patch('ai_engine.services.pool_manager.extract_place_name') as mock_extract:
            mock_extract.return_value = PlaceNameExtraction(
                place_name="Grand Egyptian Museum",
                confidence=0.5,  # Low confidence
                action="add"
            )
            
            result = await find_place_for_add(
                modification_request="Add the Grand Egyptian Museum",
                city="Giza",
                country="Egypt",
                available_places=available_places,
                preferences=None
            )
            
            assert result is None  # Should fall back to standard modifier flow

    @pytest.mark.asyncio
    async def test_hybrid_search_city_mismatch(self):
        """Test hybrid search respects city filter."""
        from ai_engine.services.pool_manager import find_place_for_add
        
        available_places = [
            {"id": "gem_001", "name": "Grand Egyptian Museum", "city": "Giza", "country": "Egypt"},
            {"id": "gem_002", "name": "Grand Egyptian Museum", "city": "Cairo", "country": "Egypt"},
        ]
        
        with patch('ai_engine.services.pool_manager.extract_place_name') as mock_extract:
            mock_extract.return_value = PlaceNameExtraction(
                place_name="Grand Egyptian Museum",
                confidence=1.0,
                action="add"
            )
            
            result = await find_place_for_add(
                modification_request="Add the Grand Egyptian Museum",
                city="Cairo",  # Request Cairo, not Giza
                country="Egypt",
                available_places=available_places,
                preferences=None
            )
            
            assert result is not None
            assert result["id"] == "gem_002"  # Should match Cairo version

    @pytest.mark.asyncio
    async def test_hybrid_search_empty_request(self):
        """Test hybrid search handles empty requests."""
        from ai_engine.services.pool_manager import find_place_for_add
        
        result = await find_place_for_add(
            modification_request="",
            city="Giza",
            country="Egypt",
            available_places=[],
            preferences=None
        )
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
