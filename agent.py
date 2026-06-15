"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """Extract description, size, and max_price from a natural language query."""
    text = query

    max_price = None
    price_match = re.search(r'under\s*\$(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if not price_match:
        price_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(?:or less|max|budget)', text, re.IGNORECASE)
    if price_match:
        max_price = float(price_match.group(1))
        text = text[:price_match.start()] + text[price_match.end():]

    size = None
    size_match = re.search(r'\bsize\s+([A-Z0-9/]+)\b', text, re.IGNORECASE)
    if size_match:
        size = size_match.group(1).upper()
        text = text[:size_match.start()] + text[size_match.end():]

    description = re.sub(r'[,.\-]+', ' ', text)
    description = re.sub(r'\s+', ' ', description).strip()
    # Remove filler phrases
    for filler in ["i'm looking for", "looking for", "find me", "i want", "i need",
                   "what's out there", "and how would i style it", "show me"]:
        description = re.sub(re.escape(filler), '', description, flags=re.IGNORECASE)
    description = re.sub(r'\s+', ' ', description).strip()

    return {"description": description, "size": size, "max_price": max_price}


def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop.
    Returns the completed session dict.
    """
    session = _new_session(query, wardrobe)

    # Step 1: Parse
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 2: Search
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        parts = [f"'{parsed['description']}'"]
        if parsed["size"]:
            parts.append(f"size {parsed['size']}")
        if parsed["max_price"]:
            parts.append(f"under ${parsed['max_price']:.0f}")
        session["error"] = (
            f"No listings found matching {', '.join(parts)}. "
            "Try broadening your search — remove the size filter, increase your budget, or use different keywords."
        )
        return session

    # Step 3: Select top result
    session["selected_item"] = results[0]

    # Step 4: Suggest outfit
    session["outfit_suggestion"] = suggest_outfit(results[0], wardrobe)

    # Step 5: Create fit card
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], results[0])

    return session


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
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
