"""Tests for chat route card selection.

These guard against duplicating structured UI cards when a response only
needs one card type, for example flight options alongside stale itinerary
state.
"""

from app.api.v1.routes.chat import _build_cards_from_ai_result


def _itinerary_with_hotels():
    return {
        "destination": "Cairo",
        "days": [
            {
                "day_number": 1,
                "stops": [{"id": "p1", "name": "Pyramids"}],
            }
        ],
        "accommodation_suggestions": [
            {"id": "h1", "name": "Hotel A"},
            {"id": "h2", "name": "Hotel B"},
        ],
    }


def test_itinerary_response_does_not_emit_hotel_options_until_hotel_phase():
    cards, _ = _build_cards_from_ai_result(
        {
            "response_type": "itinerary",
            "phase": "itinerary_review",
            "message": "Here is your itinerary",
            "itinerary": _itinerary_with_hotels(),
        },
        include_itinerary=True,
    )

    assert [card["card_type"] for card in cards] == ["itinerary"]


def test_replace_ui_action_emits_itinerary_card_for_chat_response():
    cards, _ = _build_cards_from_ai_result(
        {
            "response_type": "chat",
            "phase": "itinerary_review",
            "message": "Your itinerary is updated. See it below.",
            "itinerary": _itinerary_with_hotels(),
            "ui": {"actions": ["replace_itinerary_card"]},
        },
        include_itinerary=True,
    )

    assert [card["card_type"] for card in cards] == ["itinerary"]
    assert cards[0]["presentation"] == "replace"


def test_hotel_phase_emits_hotel_options_without_resending_itinerary_card():
    cards, _ = _build_cards_from_ai_result(
        {
            "response_type": "chat",
            "phase": "hotel_selection",
            "message": "Choose a hotel",
            "itinerary": _itinerary_with_hotels(),
        },
        include_itinerary=True,
    )

    assert [card["card_type"] for card in cards] == ["hotel_options"]
    assert cards[0]["data"]["options"][0]["name"] == "Hotel A"


def test_flight_options_response_does_not_resend_itinerary_card():
    cards, _ = _build_cards_from_ai_result(
        {
            "response_type": "chat",
            "phase": "flight_selection",
            "message": "Here are flights",
            "itinerary": _itinerary_with_hotels(),
            "flight_search_results": [{"id": "f1"}, {"id": "f2"}],
        },
        include_itinerary=True,
    )

    assert [card["card_type"] for card in cards] == ["flight_options"]
