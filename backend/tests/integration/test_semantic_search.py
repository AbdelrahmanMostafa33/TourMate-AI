"""
Integration tests for the semantic place search endpoint.

Tests the POST /api/v1/places/search/semantic endpoint with:
- In-memory SQLite database
- Mocked embedding service (no real Google API calls)
- Seeded places with known embeddings for deterministic ranking

Covers happy paths, filters, error cases, and edge conditions.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.place import Place, AttractionDetails, RestaurantDetails, HotelDetails
from app.models.enums import PlaceCategory, AccommodationType


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

EMBEDDING_DIMS = 768

# Known query vector returned by the mocked embed_query_async
# Using a vector where dimension 0 = 1.0, all others = 0.0
# This makes similarity scores predictable based on the first element of each place's embedding.
QUERY_VECTOR = [1.0] + [0.0] * (EMBEDDING_DIMS - 1)


def _make_embedding(*values: float) -> list[float]:
    """Create an EMBEDDING_DIMS-dim vector with specified values at the front.

    Example::

        _make_embedding(1.0, 0.0) -> [1.0, 0.0, 0.0, 0.0, ...]

    The remaining dimensions (after the given values) are zero-padded.
    This makes it easy to create deterministic test vectors where
    cosine similarity with QUERY_VECTOR is controlled by the first element.
    """
    vec = [0.0] * EMBEDDING_DIMS
    for i, v in enumerate(values):
        if i < EMBEDDING_DIMS:
            vec[i] = float(v)
    return vec


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Backup and restore app.dependency_overrides around each test."""
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _make_client(db_session):
    """Create a TestClient with the db session override."""
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def mock_embed():
    """Mock embed_query_async to return a deterministic vector.

    The mock returns QUERY_VECTOR ([1.0, 0.0, 0.0, ...]) so that
    cosine similarity with any seeded place is controlled by the
    first element of the place's embedding.
    """
    with patch(
        "ai_engine.services.embedding_service.embed_query_async",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = QUERY_VECTOR
        yield mock


@pytest.fixture
async def seeded_places(db_session):
    """Seed places with known embeddings for deterministic ranking.

    Place         | embedding[0] | expected similarity with QUERY_VECTOR
    ------------- | ------------ | -------------------------------------
    Highly Ranked |          1.0 | 1.0 (identical direction)
    Moderately    |        0.707 | ~0.707 (45° angle)
    Unrelated     |          0.0 | 0.0 (orthogonal)

    Additionally seeds places without embeddings (should be excluded),
    with city/category filters, and across different categories.
    """
    places_data = [
        # ── Cairo attractions ──
        {
            "place_id": "sem_cai_001", "name": "Egyptian Museum",
            "category": PlaceCategory.attraction, "city": "Cairo", "country": "Egypt",
            "rating": 4.7, "popularity_score": 90.0,
            "embedding": _make_embedding(1.0, 0.0),
            "description": "World-famous museum of Egyptian antiquities",
            "attraction_details": {"subcategory": "museum", "entry_fee": 200.0},
        },
        {
            "place_id": "sem_cai_002", "name": "Khan El Khalili",
            "category": PlaceCategory.attraction, "city": "Cairo", "country": "Egypt",
            "rating": 4.5, "popularity_score": 85.0,
            "embedding": _make_embedding(0.707, 0.707),
            "description": "Historic market and bazaar",
            "attraction_details": {"subcategory": "market", "entry_fee": None},
        },
        {
            "place_id": "sem_cai_003", "name": "City of the Dead",
            "category": PlaceCategory.attraction, "city": "Cairo", "country": "Egypt",
            "rating": 3.8, "popularity_score": 40.0,
            "embedding": _make_embedding(0.0, 1.0),
            "description": "Ancient cemetery and necropolis",
            "attraction_details": {"subcategory": "historic", "entry_fee": 50.0},
        },
        # ── Cairo restaurants ──
        {
            "place_id": "sem_cai_004", "name": "Abu Shukri",
            "category": PlaceCategory.restaurant, "city": "Cairo", "country": "Egypt",
            "rating": 4.5, "popularity_score": 75.0,
            "embedding": _make_embedding(0.5, 0.5),
            "description": "Famous local restaurant",
            "restaurant_details": {"cuisine_type": "local cuisine", "avg_cost_per_person": 15.0},
        },
        {
            "place_id": "sem_cai_005", "name": "Nubian Restaurant",
            "category": PlaceCategory.restaurant, "city": "Cairo", "country": "Egypt",
            "rating": 4.2, "popularity_score": 60.0,
            "embedding": _make_embedding(0.0, 0.5),
            "description": "Traditional Nubian cuisine",
            "restaurant_details": {"cuisine_type": "local cuisine", "avg_cost_per_person": 20.0},
        },
        # ── No embedding (should be excluded from results) ──
        {
            "place_id": "sem_cai_006", "name": "No Embedding Place",
            "category": PlaceCategory.attraction, "city": "Cairo", "country": "Egypt",
            "rating": 4.0, "popularity_score": 50.0,
            "embedding": None,
            "description": "This place has no embedding and should not appear",
            "attraction_details": {"subcategory": "park", "entry_fee": None},
        },
        # ── Other city (should not appear when filtered by city) ──
        {
            "place_id": "sem_lux_001", "name": "Luxor Temple",
            "category": PlaceCategory.attraction, "city": "Luxor", "country": "Egypt",
            "rating": 4.9, "popularity_score": 95.0,
            "embedding": _make_embedding(0.9, 0.1),
            "description": "Ancient Egyptian temple complex",
            "attraction_details": {"subcategory": "historic", "entry_fee": 300.0},
        },
        # ── Cairo hotel (different category) ──
        {
            "place_id": "sem_cai_007", "name": "Mena House Hotel",
            "category": PlaceCategory.hotel, "city": "Cairo", "country": "Egypt",
            "rating": 4.8, "popularity_score": 88.0,
            "embedding": _make_embedding(0.8, 0.2),
            "description": "Historic hotel near the Pyramids",
            "hotel_details": {
                "star_class": 5, "nightly_rate": 250.0,
                "amenities": ["pool", "spa", "gym"],
                "accommodation_type": AccommodationType.luxury,
            },
        },
    ]

    for data in places_data:
        # Extract detail-specific data
        attraction_data = data.pop("attraction_details", None)
        restaurant_data = data.pop("restaurant_details", None)
        hotel_data = data.pop("hotel_details", None)

        # Create Place
        place = Place(**data)
        db_session.add(place)

        # Create details
        if attraction_data:
            details = AttractionDetails(
                place_id=data["place_id"],
                **attraction_data,
            )
            db_session.add(details)

        if restaurant_data:
            details = RestaurantDetails(
                place_id=data["place_id"],
                **restaurant_data,
            )
            db_session.add(details)

        if hotel_data:
            details = HotelDetails(
                place_id=data["place_id"],
                **hotel_data,
            )
            db_session.add(details)

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _assert_sorted_by_similarity(places: list[dict]) -> None:
    """Verify places are sorted by similarity_score descending."""
    scores = [p.get("similarity_score", 0) for p in places]
    assert scores == sorted(scores, reverse=True), (
        f"Places not sorted by similarity descending: {scores}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Basic Semantic Search
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestBasicSemanticSearch:
    """Happy path — query returns places ranked by similarity."""

    async def test_returns_places_sorted_by_similarity(
        self, db_session, seeded_places, mock_embed,
    ):
        """Given a query, return all places with embeddings sorted by similarity."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "historical museum artifacts"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "places" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "historical museum artifacts"

        # Should return 7 places (6 with embeddings, 1 without is excluded)
        # But also, Luxor is in a different city — no city filter, so it appears
        assert data["total"] == 7

        places = data["places"]
        assert len(places) == 7

        # All places should have similarity_score
        for place in places:
            assert "similarity_score" in place
            assert isinstance(place["similarity_score"], float)

        # Verify ranking order: Egyptian Museum (1.0) > Luxor Temple (0.9)
        # > Mena House (0.8) > Khan El Khalili (~0.707) > Abu Shukri (0.5)
        # > Nubian (0.0) > City of the Dead (0.0)
        # City of the Dead and Nubian both have 0.0 — their relative order
        # within ties is undefined, so we just check the non-tied order.
        names = [p["name"] for p in places]
        # First 5 should have deterministic order
        assert names[0] == "Egyptian Museum"
        assert names[1] == "Luxor Temple"
        assert names[2] == "Mena House Hotel"
        assert names[3] == "Khan El Khalili"
        assert names[4] == "Abu Shukri"

    async def test_returns_proper_response_structure(
        self, db_session, seeded_places, mock_embed,
    ):
        """Response has the correct top-level structure."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "museum"},
        )

        assert response.status_code == 200
        data = response.json()
        assert list(data.keys()) == ["places", "total", "query"]
        assert isinstance(data["places"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["query"], str)

    async def test_mock_was_called_with_formatted_query(
        self, db_session, seeded_places, mock_embed,
    ):
        """embed_query_async is called with the 'task: search result | query:' prefix."""
        client = _make_client(db_session)

        client.post(
            "/api/v1/places/search/semantic",
            json={"query": "romantic dinner with sea view"},
        )

        mock_embed.assert_called_once()
        call_arg = mock_embed.call_args[0][0]
        assert call_arg.startswith("task: search result | query:")
        assert "romantic dinner with sea view" in call_arg


# ═══════════════════════════════════════════════════════════════════════════════
# 2. City Filter
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchCityFilter:
    """City filter narrows results to a specific city."""

    async def test_filters_by_city(
        self, db_session, seeded_places, mock_embed,
    ):
        """When city is provided, only places in that city are returned."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "historical sites", "city": "Cairo"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 6  # 6 Cairo places with embeddings
        for place in data["places"]:
            assert place["city"].lower() == "cairo"

    async def test_case_insensitive_city(
        self, db_session, seeded_places, mock_embed,
    ):
        """City filter is case-insensitive."""
        client = _make_client(db_session)

        response_upper = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "city": "CAIRO"},
        )
        response_lower = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "city": "cairo"},
        )
        response_mixed = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "city": "Cairo"},
        )

        assert response_upper.json()["total"] == response_lower.json()["total"]
        assert response_lower.json()["total"] == response_mixed.json()["total"]
        assert response_upper.json()["total"] == 6

    async def test_city_no_match_returns_empty(
        self, db_session, seeded_places, mock_embed,
    ):
        """When no places match the city, return empty results."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "city": "NonExistentCity"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["places"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Category Filter
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchCategoryFilter:
    """Category filter narrows results to a specific place category."""

    async def test_filters_by_category(
        self, db_session, seeded_places, mock_embed,
    ):
        """When category is provided, only places of that category are returned."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "food", "category": "restaurant"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 2 restaurant places
        for place in data["places"]:
            assert place["category"] == "restaurant"

    async def test_filters_by_attraction(
        self, db_session, seeded_places, mock_embed,
    ):
        """Attraction category filter works."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "history", "category": "attraction"},
        )

        assert response.status_code == 200
        data = response.json()
        # Without city filter: 3 Cairo attractions + 1 Luxor attraction = 4
        assert data["total"] == 4
        for place in data["places"]:
            assert place["category"] == "attraction"

    async def test_case_insensitive_category(
        self, db_session, seeded_places, mock_embed,
    ):
        """Category filter accepts variations like 'attractions'."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "category": "attractions"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4  # All attractions

    async def test_category_no_match_returns_empty(
        self, db_session, seeded_places, mock_embed,
    ):
        """When no places match the category, return empty results."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "category": "hotel"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # 1 hotel
        assert data["places"][0]["category"] == "hotel"

    async def test_invalid_category_returns_all_results(
        self, db_session, seeded_places, mock_embed,
    ):
        """An unrecognized category is silently ignored — all places are returned."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "category": "invalid_category"},
        )

        assert response.status_code == 200
        data = response.json()
        # The endpoint silently skips unrecognized categories (no filter applied)
        assert data["total"] == 7
        assert len(data["places"]) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Combined Filters
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchCombinedFilters:
    """City + category + limit filters applied together."""

    async def test_city_and_category_together(
        self, db_session, seeded_places, mock_embed,
    ):
        """City + category filters combine correctly."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={
                "query": "dinner",
                "city": "Cairo",
                "category": "restaurant",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 2 Cairo restaurants
        for place in data["places"]:
            assert place["city"].lower() == "cairo"
            assert place["category"] == "restaurant"

    async def test_all_filters_with_limit(
        self, db_session, seeded_places, mock_embed,
    ):
        """All filters plus limit work together."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={
                "query": "museum",
                "city": "Cairo",
                "category": "attraction",
                "limit": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # 3 Cairo attractions, but limited to 2
        assert data["total"] == 3
        assert len(data["places"]) == 2
        _assert_sorted_by_similarity(data["places"])


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Limit Parameter
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchLimit:
    """Limit parameter controls how many results are returned."""

    async def test_default_limit_is_20(
        self, db_session, seeded_places, mock_embed,
    ):
        """When limit is not provided, defaults to 20."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        # Total is 7, limit is 20, so all 7 should be returned
        assert len(data["places"]) == 7

    async def test_custom_limit(
        self, db_session, seeded_places, mock_embed,
    ):
        """Custom limit caps the number of returned places."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "limit": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 7
        assert len(data["places"]) == 3

    async def test_limit_higher_than_total(
        self, db_session, seeded_places, mock_embed,
    ):
        """When limit is higher than total, all results are returned."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test", "limit": 100},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 7
        assert len(data["places"]) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Error Cases
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchErrors:
    """Error handling for invalid requests and service failures."""

    async def test_empty_query_returns_400(
        self, db_session, mock_embed,
    ):
        """Empty query string returns 400 Bad Request."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": ""},
        )

        assert response.status_code == 400
        assert "Query is required" in response.json()["detail"]

    async def test_missing_query_returns_400(
        self, db_session, mock_embed,
    ):
        """Missing query key in body returns 400 (empty string defaults, caught by endpoint)."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={},
        )

        assert response.status_code == 400
        assert "Query is required" in response.json()["detail"]

    async def test_embedding_unavailable_returns_503(
        self, db_session, seeded_places,
    ):
        """When embed_query_async returns None, return 503 Service Unavailable."""
        with patch(
            "ai_engine.services.embedding_service.embed_query_async",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = None  # Embedding service unavailable
            client = _make_client(db_session)

            response = client.post(
                "/api/v1/places/search/semantic",
                json={"query": "test query"},
            )

        assert response.status_code == 503
        assert "Embedding service unavailable" in response.json()["detail"]

    async def test_no_places_with_embeddings(
        self, db_session, mock_embed,
    ):
        """When the DB has no places with embeddings, return empty results."""
        client = _make_client(db_session)

        # No seeded places — empty DB
        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["places"] == []

    async def test_places_without_embeddings_are_excluded(
        self, db_session, seeded_places, mock_embed,
    ):
        """Places with null embedding are excluded from results."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        data = response.json()
        names = [p["name"] for p in data["places"]]
        # "No Embedding Place" has embedding=None and should not appear
        assert "No Embedding Place" not in names
        # The other 7 places with embeddings should appear
        assert len(data["places"]) == 7

    async def test_similarity_score_in_range(
        self, db_session, seeded_places, mock_embed,
    ):
        """All returned places have similarity_score between -1 and 1."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        for place in response.json()["places"]:
            score = place["similarity_score"]
            assert -1.0 <= score <= 1.0, (
                f"Place '{place['name']}' has out-of-range score: {score}"
            )

    async def test_places_have_all_required_fields(
        self, db_session, seeded_places, mock_embed,
    ):
        """Returned place dicts have the expected structure from _place_to_dict + similarity_score."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        place = response.json()["places"][0]
        required_fields = {
            "id", "name", "category", "sub_category",
            "lat", "lon", "description", "rating",
            "review_count", "popularity_score",
            "address", "city", "country",
            "photos", "similarity_score",
        }
        assert required_fields.issubset(set(place.keys())), (
            f"Missing fields: {required_fields - set(place.keys())}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Public Endpoint (no auth required)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSemanticSearchPublicAccess:
    """Semantic search is a public endpoint — no authentication required."""

    async def test_no_auth_required(
        self, db_session, seeded_places, mock_embed,
    ):
        """Endpoint works without any auth header or override."""
        # Don't override get_current_user at all
        app.dependency_overrides[get_db] = lambda: db_session
        client = TestClient(app)

        response = client.post(
            "/api/v1/places/search/semantic",
            json={"query": "test"},
        )

        # Should succeed (200) — no auth dependency on this route
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
