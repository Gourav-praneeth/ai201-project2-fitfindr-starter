"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex. No LLM call needed for this step.

    Examples:
        "vintage graphic tee under $30"        → desc="vintage graphic tee", max_price=30.0
        "90s track jacket in size M"           → desc="90s track jacket", size="M"
        "designer ballgown size XXS under $5"  → desc="designer ballgown", size="XXS", max_price=5.0
    """
    # --- max_price ---
    max_price = None
    price_match = re.search(r'under\s+\$?(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if not price_match:
        price_match = re.search(r'\$(\d+(?:\.\d+)?)', query, re.IGNORECASE)
    if price_match:
        max_price = float(price_match.group(1))

    # --- size ---
    size = None
    # First try explicit "size <token>" pattern
    size_explicit = re.search(r'\bsize\s+(\S+)', query, re.IGNORECASE)
    if size_explicit:
        size = size_explicit.group(1).upper()
    else:
        # Fall back to standalone size tokens (covers XS, S/M, XL, W30, W30 L30, US 8, etc.)
        size_token = re.search(
            r'\b(XXS|XXL|XL|XS|S/M|M/L|[SML]|W\d{2}(?:\s*L\d{2})?|US\s*\d{1,2}(?:\.\d)?)\b',
            query,
            re.IGNORECASE,
        )
        if size_token:
            size = size_token.group(1).upper().replace(" ", "")

    # --- description: strip size/price phrases and common filler openers ---
    desc = query
    desc = re.sub(r'under\s+\$?\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\$\d+(?:\.\d+)?', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\bsize\s+\S+', '', desc, flags=re.IGNORECASE)
    # Strip filler openers like "I'm looking for", "find me a", etc.
    desc = re.sub(
        r"^(?:i'm\s+)?(?:looking\s+for|find\s+me|i\s+want|i\s+need)\s+(?:an?\s+)?",
        '',
        desc.strip(),
        flags=re.IGNORECASE,
    )
    desc = re.sub(r'\s+', ' ', desc).strip(' ,.-')

    return {
        "description": desc if desc else query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search for listings; exit early if nothing matches
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        desc = parsed["description"]
        price_hint = f" under ${parsed['max_price']:.0f}" if parsed["max_price"] else ""
        size_hint = f" in size {parsed['size']}" if parsed["size"] else ""
        session["error"] = (
            f"I couldn't find any '{desc}' listings{size_hint}{price_hint}. "
            "Try a higher budget, a broader style term, or leave out the size filter."
        )
        return session  # STOP — do not call suggest_outfit or create_fit_card

    # Step 4: Select the top-ranked result
    session["selected_item"] = results[0]

    # Step 5: Generate outfit suggestion using the selected item and wardrobe
    outfit = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    session["outfit_suggestion"] = outfit

    # Step 6: Generate the fit card caption from the outfit and item
    fit_card = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )
    session["fit_card"] = fit_card

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Parsed:  {session['parsed']}")
        print(f"Found:   {session['selected_item']['title']}  (id: {session['selected_item']['id']})")
        print(f"\nOutfit suggestion:\n{session['outfit_suggestion']}")
        print(f"\nFit card:\n{session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message:       {session2['error']}")
    print(f"selected_item:       {session2['selected_item']}")   # must be None
    print(f"outfit_suggestion:   {session2['outfit_suggestion']}") # must be None
    print(f"fit_card:            {session2['fit_card']}")          # must be None
