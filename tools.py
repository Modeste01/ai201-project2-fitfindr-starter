"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Returns a list of matching listing dicts sorted by relevance (best first).
    Returns an empty list if nothing matches.
    """
    listings = load_listings()
    keywords = description.lower().split()

    results = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.upper() not in item["size"].upper():
            continue

        searchable = (
            item["title"].lower() + " " +
            item["description"].lower() + " " +
            " ".join(item["style_tags"]).lower() + " " +
            item["category"].lower() + " " +
            " ".join(item["colors"]).lower() + " " +
            (item["brand"] or "").lower()
        )
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results]


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1-2 complete outfits.
    If wardrobe is empty, provides general styling advice.
    """
    client = _get_groq_client()

    item_desc = (
        f"{new_item['title']} — {new_item['description']}. "
        f"Category: {new_item['category']}. Colors: {', '.join(new_item['colors'])}. "
        f"Style: {', '.join(new_item['style_tags'])}."
    )

    if not wardrobe.get("items"):
        prompt = (
            f"I just found this thrifted piece: {item_desc}\n\n"
            "I don't have a wardrobe on file yet. Give me general styling advice — "
            "what types of pieces would pair well with this item? Suggest 1-2 complete "
            "outfit ideas using generic wardrobe staples. Keep it concise (3-5 sentences)."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {w['name']} ({w['category']}, {', '.join(w['colors'])})"
            for w in wardrobe["items"]
        )
        prompt = (
            f"I just found this thrifted piece: {item_desc}\n\n"
            f"Here's what I already own:\n{wardrobe_text}\n\n"
            "Suggest 1-2 complete outfit combinations using specific pieces from my "
            "wardrobe plus this new item. Be specific about which pieces to pair. "
            "Include styling tips (tucking, layering, accessories). Keep it concise (3-5 sentences)."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        category = new_item.get("category", "piece")
        return (
            f"Could not generate outfit suggestions right now. "
            f"This {category} would pair well with neutral basics and layering pieces."
        )


def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.
    Returns an error message string if outfit is empty.
    """
    if not outfit or not outfit.strip():
        return "Could not generate a fit card — no outfit suggestion was provided. Try running the full flow again."

    client = _get_groq_client()

    prompt = (
        f"Write a 2-3 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"The item: {new_item['title']}, ${new_item['price']:.0f} from {new_item['platform']}.\n"
        f"The outfit: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person posting an OOTD, not a product listing\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the vibe in specific terms\n"
        "- 2-3 sentences max, casual tone, can include 1-2 emojis\n"
        "- No hashtags"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"just thrifted this {new_item['title']} for ${new_item['price']:.0f} on {new_item['platform']} and i'm obsessed"
