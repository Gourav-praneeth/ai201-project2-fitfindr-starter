"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()
    keywords = [kw for kw in description.lower().split() if len(kw) > 1]

    scored = []
    for listing in listings:
        # Price filter
        if max_price is not None and listing["price"] > max_price:
            continue
        # Size filter — case-insensitive substring match
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        # Build a single searchable text blob from title, description, style_tags
        searchable = " ".join([
            listing["title"],
            listing["description"],
            " ".join(listing["style_tags"]),
        ]).lower()

        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_summary = (
        f"Name: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Condition: {new_item['condition']}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            "You are a fashion stylist. A user is considering buying this thrifted item:\n\n"
            f"{item_summary}\n\n"
            "They don't have any wardrobe items saved yet. Give them general styling advice: "
            "what kinds of pieces pair well with this item, what vibe it suits, and 1–2 outfit "
            "ideas using common wardrobe basics. Keep it conversational and to 3–4 sentences."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {item['name']} "
            f"(category: {item['category']}, "
            f"colors: {', '.join(item['colors'])}, "
            f"tags: {', '.join(item['style_tags'])})"
            for item in wardrobe_items
        )
        prompt = (
            "You are a fashion stylist. A user is considering buying this thrifted item:\n\n"
            f"{item_summary}\n\n"
            "Their current wardrobe contains:\n"
            f"{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific named "
            "pieces from the wardrobe above. Call each piece by name. Explain briefly why the "
            "combination works. Keep it to 4–6 sentences total."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    if not outfit or not outfit.strip():
        return (
            "Error: no outfit suggestion provided — "
            "run suggest_outfit first before calling create_fit_card."
        )

    client = _get_groq_client()

    prompt = (
        "You are writing a casual, authentic OOTD caption for someone who just found a thrift "
        "gem. Sound like a real person posting on Instagram or TikTok — not a product ad.\n\n"
        f"Thrift find:\n"
        f"- Item: {new_item['title']}\n"
        f"- Price: ${new_item['price']:.2f}\n"
        f"- Found on: {new_item['platform']}\n"
        f"- Colors: {', '.join(new_item['colors'])}\n"
        f"- Condition: {new_item['condition']}\n\n"
        f"Outfit:\n{outfit}\n\n"
        "Write a 2–4 sentence caption that:\n"
        "- Mentions the item name, price, and platform naturally (once each)\n"
        "- Captures the specific vibe of the outfit\n"
        "- Sounds fresh and personal, not generic\n"
        "Write only the caption — no hashtags, no intro like 'Here's a caption:'."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
    )
    return response.choices[0].message.content.strip()
