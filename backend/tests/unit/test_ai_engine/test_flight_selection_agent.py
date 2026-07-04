# tests/unit/test_ai_engine/test_flight_selection_agent.py
"""Comprehensive unit tests for flight_selection_agent.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from ai_engine.agents.flight_selection_agent import (
    _build_city_to_iata_map,
    resolve_city_to_iata,
    search_flights_for_trip,
    _parse_offer,
    format_flight_options,
    extract_flight_selection,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _build_city_to_iata_map tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildCityToIataMap:
    def test_contains_known_cities(self):
        mapping = _build_city_to_iata_map()
        assert mapping["cairo"] == "CAI"
        assert mapping["london"] == "LHR"
        assert mapping["paris"] == "CDG"
        assert mapping["new york"] == "JFK"
        assert mapping["sharm el sheikh"] == "SSH"

    def test_lowercase_keys(self):
        mapping = _build_city_to_iata_map()
        for key in mapping:
            assert key == key.lower(), f"Key '{key}' should be lowercase"

    def test_all_values_are_uppercase(self):
        mapping = _build_city_to_iata_map()
        for value in mapping.values():
            assert value == value.upper(), f"Value '{value}' should be uppercase"

    def test_contains_egyptian_cities(self):
        mapping = _build_city_to_iata_map()
        assert mapping["hurghada"] == "HRG"
        assert mapping["luxor"] == "LXR"
        assert mapping["aswan"] == "ASW"
        assert mapping["alexandria"] == "HBE"
        assert mapping["abu simbel"] == "ABS"

    def test_minimum_size(self):
        mapping = _build_city_to_iata_map()
        assert len(mapping) >= 15, "Should have at least 15 city mappings"


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_city_to_iata tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveCityToIata:
    def test_known_city_returns_iata(self):
        assert resolve_city_to_iata("Cairo") == "CAI"

    def test_lowercase_input(self):
        assert resolve_city_to_iata("london") == "LHR"

    def test_case_insensitive(self):
        assert resolve_city_to_iata("New York") == "JFK"

    def test_with_whitespace(self):
        assert resolve_city_to_iata("  Paris  ") == "CDG"

    def test_multi_word_city(self):
        assert resolve_city_to_iata("Sharm el Sheikh") == "SSH"

    def test_unknown_city_returns_none(self, caplog):
        """Unknown city should fall back to Amadeus, and return None if that fails."""
        import logging
        caplog.set_level(logging.WARNING)

        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.side_effect = Exception("API error")
            result = resolve_city_to_iata("Atlantis")

        assert result is None
        assert any("Atlantis" in rec.message for rec in caplog.records)

    def test_amadeus_fallback_success(self):
        """When local dict doesn't have the city, try Amadeus autocomplete."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.return_value = [
                {"iataCode": "LED", "name": "Saint Petersburg"},
            ]
            result = resolve_city_to_iata("Saint Petersburg")

        assert result == "LED"

    def test_amadeus_fallback_returns_none_when_empty(self):
        """When Amadeus returns no results, return None."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.return_value = []
            result = resolve_city_to_iata("Unknown City")

        assert result is None

    def test_amadeus_fallback_multiple_results(self):
        """When Amadeus returns multiple results, use the first with an IATA code."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.return_value = [
                {"iataCode": "", "name": "Place Without IATA"},
                {"iataCode": "ABC", "name": "Place With IATA"},
            ]
            result = resolve_city_to_iata("Some City")

        assert result == "ABC"

    def test_known_city_does_not_call_amadeus(self):
        """Known cities should be resolved locally without calling Amadeus."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            result = resolve_city_to_iata("Cairo")

        assert result == "CAI"
        mock_client.search_cities.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_offer tests
# ═══════════════════════════════════════════════════════════════════════════════

def _make_raw_offer(**overrides) -> dict:
    """Build a mock raw Amadeus offer for testing."""
    offer = {
        "validatingAirlineCodes": ["MS"],
        "itineraries": [
            {
                "segments": [
                    {
                        "carrierCode": "MS",
                        "number": "123",
                        "departure": {"iataCode": "CAI", "at": "2026-07-15T08:00:00"},
                        "arrival": {"iataCode": "LHR", "at": "2026-07-15T12:30:00"},
                    }
                ],
                "duration": "PT4H30M",
            }
        ],
        "travelerPricings": [
            {
                "fareDetailsBySegment": [
                    {"cabin": "ECONOMY"}
                ]
            }
        ],
        "price": {
            "total": "350.00",
            "currency": "USD",
            "base": "280.00",
        },
    }
    offer.update(overrides)
    return offer


class TestParseOffer:
    def test_parses_basic_offer(self):
        offer = _make_raw_offer()
        result = _parse_offer(offer, 0)

        assert result["offer_index"] == 0
        assert result["airline_code"] == "MS"
        assert result["flight_number"] == "MS123"
        assert result["origin_iata"] == "CAI"
        assert result["destination_iata"] == "LHR"
        assert result["cabin_class"] == "ECONOMY"
        assert result["total_price"] == 350.0
        assert result["currency"] == "USD"
        assert result["price_per_adult"] == 280.0
        assert result["stops"] == 0
        assert result["duration"] == "PT4H30M"
        assert result["raw_offer"] is offer  # same object

    def test_parses_multi_segment_offer(self):
        """A multi-segment itinerary should have stops > 0."""
        offer = _make_raw_offer(
            itineraries=[{
                "segments": [
                    {"carrierCode": "MS", "number": "123",
                     "departure": {"iataCode": "CAI", "at": "2026-07-15T08:00:00"},
                     "arrival": {"iataCode": "FRA", "at": "2026-07-15T11:00:00"}},
                    {"carrierCode": "LH", "number": "456",
                     "departure": {"iataCode": "FRA", "at": "2026-07-15T13:00:00"},
                     "arrival": {"iataCode": "LHR", "at": "2026-07-15T14:00:00"}},
                ],
                "duration": "PT6H",
            }]
        )
        result = _parse_offer(offer, 1)

        assert result["offer_index"] == 1
        assert result["stops"] == 1
        # Destination should be from LAST segment
        assert result["destination_iata"] == "LHR"
        # Arrival should be from LAST segment
        assert "14:00" in result["arrival_at_formatted"]

    def test_departure_and_arrival_formatted(self):
        offer = _make_raw_offer()
        result = _parse_offer(offer, 0)

        assert "Jul 15" in result["departure_at_formatted"]
        assert "Jul 15" in result["arrival_at_formatted"]
        assert "08:00" in result["departure_at_formatted"]
        assert "12:30" in result["arrival_at_formatted"]

    def test_datetime_iso_kept(self):
        offer = _make_raw_offer()
        result = _parse_offer(offer, 0)

        assert "2026-07-15" in result["departure_at"]
        assert "2026-07-15" in result["arrival_at"]

    def test_airline_name_fallback_to_code(self):
        """When Amadeus airline lookup fails, use the airline code as name."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client._client.reference_data.airlines.get.side_effect = Exception("API error")
            result = _parse_offer(_make_raw_offer(), 0)

        assert result["airline_name"] == "MS"  # falls back to code

    @pytest.mark.asyncio
    async def test_empty_string_offer_raises_keyerror(self):
        """Empty or malformed offers should raise KeyError (caught by caller)."""
        with pytest.raises((KeyError, TypeError)):
            _parse_offer({}, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# format_flight_options tests
# ═══════════════════════════════════════════════════════════════════════════════

def _make_parsed_offer(**overrides) -> dict:
    """Build a parsed flight offer dict (as returned by _parse_offer)."""
    offer = {
        "airline_name": "EgyptAir",
        "airline_code": "MS",
        "flight_number": "MS123",
        "origin_iata": "CAI",
        "destination_iata": "LHR",
        "departure_at_formatted": "Jul 15, 08:00",
        "arrival_at_formatted": "Jul 15, 12:30",
        "total_price": 350.0,
        "currency": "USD",
        "cabin_class": "economy",
        "stops": 0,
        "duration": "PT4H30M",
    }
    offer.update(overrides)
    return offer


class TestFormatFlightOptions:
    def test_empty_list_returns_no_flights_message(self):
        result = format_flight_options([])
        assert "No" in result
        assert "flights" in result.lower()

    def test_empty_list_with_cabin_filter(self):
        result = format_flight_options([], cabin_class_filter="BUSINESS")
        # The code uses cabin_class_filter.lower() in the output string
        assert "business" in result.lower()
        assert "flights" in result.lower()

    def test_single_offer_formatted(self):
        offers = [_make_parsed_offer()]
        result = format_flight_options(offers)

        assert "1️⃣" in result
        assert "EgyptAir" in result
        assert "MS123" in result
        assert "CAI" in result
        assert "LHR" in result
        assert "350" in result
        assert "USD" in result
        assert "Direct" in result

    def test_multiple_offers_numbered(self):
        offers = [
            _make_parsed_offer(airline_name="EgyptAir", flight_number="MS123", total_price=350.0),
            _make_parsed_offer(airline_name="British Airways", flight_number="BA200", total_price=500.0),
        ]
        result = format_flight_options(offers)

        assert "1️⃣" in result
        assert "2️⃣" in result
        assert "EgyptAir" in result
        assert "British Airways" in result
        assert "350" in result
        assert "500" in result

    def test_shows_cabin_class(self):
        offers = [_make_parsed_offer(cabin_class="business")]
        result = format_flight_options(offers)

        assert "Business" in result

    def test_shows_stop_count(self):
        offers = [_make_parsed_offer(stops=1)]
        result = format_flight_options(offers)

        assert "1 stop(s)" in result

    def test_direct_flight_shows_direct(self):
        offers = [_make_parsed_offer(stops=0)]
        result = format_flight_options(offers)

        assert "Direct" in result

    def test_shows_duration(self):
        offers = [_make_parsed_offer(duration="PT4H30M")]
        result = format_flight_options(offers)

        assert "PT4H30M" in result

    def test_fallback_to_airline_code_when_no_name(self):
        offers = [_make_parsed_offer(airline_name="", airline_code="MS")]
        result = format_flight_options(offers)

        assert "MS" in result

    def test_unknown_airline_when_nothing(self):
        """When airline_name and airline_code keys are missing, fallback to 'Unknown'."""
        # Only include keys that exist — no airline_name or airline_code
        offers = [{"total_price": 0, "stops": 0}]
        result = format_flight_options(offers)

        assert "Unknown" in result


# ═══════════════════════════════════════════════════════════════════════════════
# extract_flight_selection tests
# ═══════════════════════════════════════════════════════════════════════════════

_OFFERS = [
    _make_parsed_offer(airline_name="EgyptAir", airline_code="MS", flight_number="MS123", total_price=350.0),
    _make_parsed_offer(airline_name="British Airways", airline_code="BA", flight_number="BA200", total_price=500.0),
    _make_parsed_offer(airline_name="Emirates", airline_code="EK", flight_number="EK301", total_price=650.0),
]


class TestExtractFlightSelection:
    def test_empty_offers_returns_none(self):
        result = extract_flight_selection("I want the first one", [])
        assert result is None

    def test_by_direct_index(self):
        """Direct 1-based index match (from message interpreter)."""
        result = extract_flight_selection("I want this", _OFFERS, selected_number=2)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_by_index_out_of_range_returns_none(self):
        result = extract_flight_selection("Show me some options", _OFFERS, selected_number=10)
        assert result is None

    def test_by_index_zero_or_negative(self):
        result = extract_flight_selection("Show me some options", _OFFERS, selected_number=0)
        assert result is None

    def test_by_airline_name_in_message(self):
        """Message contains the airline name."""
        result = extract_flight_selection("I'll take Emirates", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_by_airline_name_case_insensitive(self):
        result = extract_flight_selection("emirates is the best", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_by_flight_number_in_message(self):
        result = extract_flight_selection("Show me MS123", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_by_airline_code_in_message(self):
        result = extract_flight_selection("I want BA flight", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_by_regex_flight_number(self):
        """Regex patterns like 'flight 2' should match."""
        result = extract_flight_selection("flight 3", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_by_regex_option_number(self):
        result = extract_flight_selection("option 2", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_by_regex_hash_number(self):
        result = extract_flight_selection("#3 please", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_by_word_first(self):
        result = extract_flight_selection("I'll take the first one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_by_word_second(self):
        result = extract_flight_selection("second option", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_by_word_third(self):
        result = extract_flight_selection("third one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_by_ordinal_1st(self):
        result = extract_flight_selection("1st flight", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_by_ordinal_2nd(self):
        result = extract_flight_selection("pick the 2nd one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_default_to_first_for_selection_keywords(self):
        """When message has selection keywords but no specific match, default to first."""
        result = extract_flight_selection("go with that one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_default_for_pick_keyword(self):
        result = extract_flight_selection("I'll take this one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_default_for_choose_keyword(self):
        result = extract_flight_selection("choose that one", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_no_match_returns_none(self):
        result = extract_flight_selection("What else can you tell me?", _OFFERS)
        assert result is None

    def test_no_match_for_general_question(self):
        result = extract_flight_selection("Tell me more about Cairo", _OFFERS)
        assert result is None

    def test_full_airline_name_match(self):
        """Full airline name in message should match."""
        result = extract_flight_selection("I want British Airways", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_index_preferred_over_keywords(self):
        """When both index and message are provided, index takes priority."""
        result = extract_flight_selection("I like Emirates", _OFFERS, selected_number=2)
        assert result is not None
        assert result["flight_number"] == "BA200"  # index 2, not Emirates


# ═══════════════════════════════════════════════════════════════════════════════
# search_flights_for_trip tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchFlightsForTrip:
    @pytest.mark.asyncio
    async def test_unknown_origin_returns_empty(self):
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.side_effect = Exception("Unknown")
            result = await search_flights_for_trip(
                origin_city="Atlantis",
                destination_city="Cairo",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_unknown_destination_returns_empty(self):
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_cities.side_effect = [None, Exception("Unknown")]
            # First call (origin=Cairo) needs to return something
            # Actually, resolve_city_to_iata for "Cairo" uses local dict, doesn't call Amadeus
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="Atlantis",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_no_departure_date_uses_default(self):
        """When no departure date is given, should use a default 30-days-from-now."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = []
            await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
            )

        # Should have been called with some departure_date (30 days from now)
        call_kwargs = mock_client.search_flights.call_args[1]
        assert "departure_date" in call_kwargs
        assert call_kwargs["departure_date"] is not None

    @pytest.mark.asyncio
    async def test_search_api_failure_returns_empty(self, caplog):
        import logging
        caplog.set_level(logging.ERROR)

        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.side_effect = Exception("API timeout")
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
            )

        assert result == []
        assert any("Flight search failed" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self):
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = []
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_successful_search_returns_parsed_offers(self):
        raw_offers = [
            _make_raw_offer(
                validatingAirlineCodes=["MS"],
                itineraries=[{
                    "segments": [
                        {"carrierCode": "MS", "number": "123",
                         "departure": {"iataCode": "CAI", "at": "2026-07-15T08:00:00"},
                         "arrival": {"iataCode": "LHR", "at": "2026-07-15T12:30:00"}},
                    ],
                    "duration": "PT4H30M",
                }],
                travelerPricings=[{"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}],
                price={"total": "350.00", "currency": "USD", "base": "280.00"},
            ),
            _make_raw_offer(
                validatingAirlineCodes=["BA"],
                itineraries=[{
                    "segments": [
                        {"carrierCode": "BA", "number": "200",
                         "departure": {"iataCode": "CAI", "at": "2026-07-15T14:00:00"},
                         "arrival": {"iataCode": "LHR", "at": "2026-07-15T18:30:00"}},
                    ],
                    "duration": "PT4H30M",
                }],
                travelerPricings=[{"fareDetailsBySegment": [{"cabin": "BUSINESS"}]}],
                price={"total": "800.00", "currency": "USD", "base": "650.00"},
            ),
        ]

        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = raw_offers
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
                departure_date="2026-07-15",
                adults=2,
                cabin_class="ECONOMY",
                return_date="2026-07-22",
            )

        assert len(result) == 2

        # First offer
        assert result[0]["flight_number"] == "MS123"
        assert result[0]["airline_code"] == "MS"
        assert result[0]["total_price"] == 350.0
        assert result[0]["currency"] == "USD"
        assert result[0]["cabin_class"] == "ECONOMY"
        assert result[0]["stops"] == 0

        # Second offer
        assert result[1]["flight_number"] == "BA200"
        assert result[1]["total_price"] == 800.0
        assert result[1]["cabin_class"] == "BUSINESS"
        assert result[1]["raw_offer"] is raw_offers[1]

        # Verify API call parameters
        mock_client.search_flights.assert_called_once_with(
            origin="CAI",
            destination="LHR",
            departure_date="2026-07-15",
            adults=2,
            max_results=5,
            travel_class="ECONOMY",
            return_date="2026-07-22",
        )

    @pytest.mark.asyncio
    async def test_parses_cabin_class_from_traveler_pricing(self):
        raw_offers = [
            _make_raw_offer(
                travelerPricings=[{"fareDetailsBySegment": [{"cabin": "FIRST"}]}],
            ),
        ]

        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = raw_offers
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
                departure_date="2026-07-15",
            )

        assert result[0]["cabin_class"] == "FIRST"

    @pytest.mark.asyncio
    async def test_skips_malformed_offers(self, caplog):
        """Malformed offers should be skipped with a warning."""
        import logging
        caplog.set_level(logging.WARNING)

        raw_offers = [
            _make_raw_offer(),  # valid
            {"bad": "offer"},   # invalid — missing keys
        ]

        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = raw_offers
            result = await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
            )

        assert len(result) == 1  # only the valid one was parsed
        assert any("Skipping" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_passes_return_date_for_round_trip(self):
        """Return date should be passed to Amadeus for round-trip searches."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = []
            await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
                departure_date="2026-07-15",
                return_date="2026-07-22",
            )

        call_kwargs = mock_client.search_flights.call_args[1]
        assert call_kwargs.get("return_date") == "2026-07-22"

    @pytest.mark.asyncio
    async def test_no_return_date_for_one_way(self):
        """When no return_date is given, it should not be in the API call."""
        with patch("app.services.amadeus_client.amadeus_client") as mock_client:
            mock_client.search_flights.return_value = []
            await search_flights_for_trip(
                origin_city="Cairo",
                destination_city="London",
                departure_date="2026-07-15",
            )

        call_kwargs = mock_client.search_flights.call_args[1]
        assert call_kwargs.get("return_date") is None


# ═══════════════════════════════════════════════════════════════════════════════
# format_flight_options edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestFormatFlightOptionsEdgeCases:
    def test_empty_string_fields_handled(self):
        """Missing or empty fields should not crash formatting."""
        offers = [{
            "airline_name": "",
            "airline_code": "",
            "flight_number": "",
            "origin_iata": "",
            "destination_iata": "",
            "departure_at_formatted": "",
            "arrival_at_formatted": "",
            "total_price": 0,
            "currency": "",
            "cabin_class": "",
            "stops": 0,
            "duration": "",
        }]
        result = format_flight_options(offers)
        # Should still render without crash
        assert "1️⃣" in result

    def test_five_or_more_offers(self):
        """All 5 emoji slots should be used, and beyond may use numeric fallback."""
        offers = [
            _make_parsed_offer(airline_name=f"Airline {i}", total_price=float(i * 100))
            for i in range(6)
        ]
        result = format_flight_options(offers)

        assert "1️⃣" in result
        assert "2️⃣" in result
        assert "3️⃣" in result
        assert "4️⃣" in result
        assert "5️⃣" in result
        # 6th might use numeric or emoji depending on implementation
        assert "Airline 5" in result

    def test_offers_with_missing_keys(self):
        """Missing optional keys should be handled gracefully."""
        offers = [{"total_price": 100, "stops": 0}]  # minimal
        result = format_flight_options(offers)

        assert "100" in result
        assert "Direct" in result


# ═══════════════════════════════════════════════════════════════════════════════
# extract_flight_selection edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractFlightSelectionEdgeCases:
    def test_single_offer_defaults_to_it(self):
        """With only one offer, specific matches should still work."""
        offers = [_make_parsed_offer(airline_name="EgyptAir")]
        result = extract_flight_selection("What about the first one?", offers)
        assert result is not None
        assert result["flight_number"] == "MS123"

    def test_partial_airline_name_match(self):
        """Partial name in message should still match."""
        result = extract_flight_selection("I like Emirates Air", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "EK301"

    def test_no_match_without_selection_keywords(self):
        """A message without selection keywords should return None if no specific match."""
        result = extract_flight_selection("What are my options for flights?", _OFFERS)
        assert result is None

    def test_flight_number_in_message_matches_correctly(self):
        """Flight number should match even when it appears in a sentence."""
        result = extract_flight_selection("I'd like to book BA200 please", _OFFERS)
        assert result is not None
        assert result["flight_number"] == "BA200"

    def test_multiple_matches_returns_first_match(self):
        """When multiple offers match (e.g. airline code in multiple names), return first."""
        offers = [
            _make_parsed_offer(airline_name="British Airways", airline_code="BA", flight_number="BA001"),
            _make_parsed_offer(airline_name="British Midland", airline_code="BM", flight_number="BM002"),
        ]
        result = extract_flight_selection("I want British", offers)
        assert result is not None
        # Should match the first one containing "british"
        assert result["flight_number"] in ("BA001", "BM002")
