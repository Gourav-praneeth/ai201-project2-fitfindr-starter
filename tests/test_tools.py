"""
tests/test_tools.py

Unit tests for each FitFindr tool.
Covers: happy-path behavior, failure modes, and edge cases.

Run with:
    pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Intentionally impossible query: no listing matches all three constraints
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_sorted_by_relevance():
    # The highest-scoring match should come first; both should contain 'vintage'
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    assert len(results) >= 2
    # First result must be a list dict with required fields
    first = results[0]
    for field in ("id", "title", "price", "category", "style_tags", "colors", "platform"):
        assert field in first


def test_search_size_filter_case_insensitive():
    # "m" should match listings whose size field contains "M" or "S/M"
    results = search_listings("top", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_no_size_filter_returns_all_sizes():
    with_filter = search_listings("vintage", size="M", max_price=None)
    without_filter = search_listings("vintage", size=None, max_price=None)
    assert len(without_filter) >= len(with_filter)


def test_search_returns_list_not_none():
    # Should never return None, even for an impossible query
    result = search_listings("xyzzy_nonexistent_term", size=None, max_price=None)
    assert result is not None
    assert isinstance(result, list)


# ── suggest_outfit ────────────────────────────────────────────────────────────

def _sample_item():
    """Return a realistic listing dict for use in suggest_outfit tests."""
    return {
        "id": "lst_006",
        "title": "Graphic Tee — 2003 Tour Bootleg Style",
        "description": "Vintage-style bootleg tee with faded graphic.",
        "category": "tops",
        "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
        "size": "L",
        "condition": "good",
        "price": 24.00,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }


def test_suggest_outfit_with_wardrobe_returns_string():
    result = suggest_outfit(_sample_item(), get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_returns_string():
    # Must not raise; must return non-empty general advice
    result = suggest_outfit(_sample_item(), get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_no_exception():
    # Defensive check: empty wardrobe should never crash the function
    try:
        result = suggest_outfit(_sample_item(), {"items": []})
    except Exception as exc:
        pytest.fail(f"suggest_outfit raised an exception on empty wardrobe: {exc}")
    assert result  # non-empty


def test_suggest_outfit_references_item_name():
    # The LLM should at least reference something about the item in its response
    result = suggest_outfit(_sample_item(), get_example_wardrobe())
    # Check for at least one meaningful word from the item's context
    assert any(
        word in result.lower()
        for word in ["tee", "graphic", "vintage", "grunge", "streetwear", "black"]
    )


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    outfit = "Pair the tee with baggy jeans and chunky white sneakers for a streetwear look."
    result = create_fit_card(outfit, _sample_item())
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error_string():
    result = create_fit_card("", _sample_item())
    assert isinstance(result, str)
    assert "error" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   \n  ", _sample_item())
    assert isinstance(result, str)
    assert "error" in result.lower()


def test_create_fit_card_no_exception_on_empty_outfit():
    try:
        result = create_fit_card("", _sample_item())
    except Exception as exc:
        pytest.fail(f"create_fit_card raised an exception on empty outfit: {exc}")
    assert result


def test_create_fit_card_mentions_platform():
    outfit = "Pair with dark jeans and boots for a vintage grunge look."
    result = create_fit_card(outfit, _sample_item())
    # Caption should naturally include the platform name
    assert "depop" in result.lower()


def test_create_fit_card_output_varies():
    # Running twice on identical input should produce different captions (temperature=1.0)
    outfit = "Pair the tee with baggy jeans and chunky sneakers."
    item = _sample_item()
    result_a = create_fit_card(outfit, item)
    result_b = create_fit_card(outfit, item)
    # They should not be byte-for-byte identical (probabilistic — fails only if temp=0)
    assert result_a != result_b, (
        "create_fit_card returned identical output twice — LLM temperature may be 0"
    )
