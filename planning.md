# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items matching a text description, optional size filter, and optional maximum price. Returns results ranked by keyword relevance.

**Input parameters:**
- `description` (str): Keywords describing the desired item (e.g., "vintage graphic tee")
- `size` (str | None): Size to filter by (case-insensitive substring match, e.g., "M" matches "S/M"). None skips size filtering.
- `max_price` (float | None): Maximum price inclusive. None skips price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict contains: id, title, description, category, style_tags (list[str]), size, condition, price (float), colors (list[str]), brand (str|None), platform. Returns an empty list `[]` if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a message like "No listings found matching 'vintage graphic tee' under $30 in size M. Try broadening your search — remove the size filter or increase your budget." The agent does NOT proceed to suggest_outfit. It returns the session early so the user sees actionable feedback.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item and the user's current wardrobe, calls the LLM to suggest 1–2 complete outfit combinations using specific pieces from the wardrobe. If the wardrobe is empty, provides general styling advice instead.

**Input parameters:**
- `new_item` (dict): A listing dict representing the item the user is considering (contains title, description, colors, style_tags, category, etc.)
- `wardrobe` (dict): A dict with an `items` key containing a list of wardrobe item dicts. Each item has: id, name, category, colors, style_tags, notes.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. When the wardrobe has items, it references them by name (e.g., "Pair this with your baggy straight-leg jeans and white ribbed tank top"). When the wardrobe is empty, it offers general styling advice for the item's vibe (what types of pieces pair well).

**What happens if it fails or returns nothing:**
If wardrobe['items'] is empty, the tool still returns useful output (general styling advice) — this is handled within the tool itself, not treated as a failure. If the LLM call itself fails (network error, API error), the tool catches the exception and returns a fallback string: "Could not generate outfit suggestions right now. This [item category] would pair well with [generic complementary items based on category]."

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable Instagram/TikTok-style caption for a complete outfit featuring the thrifted item. Uses higher LLM temperature to produce varied output.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from suggest_outfit()
- `new_item` (dict): The listing dict for the thrifted item (used to extract title, price, platform)

**What it returns:**
A 2–4 sentence casual caption that mentions the item name, price, and platform naturally. Sounds like a real person's OOTD post, not a product description.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns the error string: "Could not generate a fit card — no outfit suggestion was provided. Try running the full flow again." Does not call the LLM with empty input. If the LLM call fails, returns a simple fallback caption built from the item's title and price.

---

### Additional Tools (if any)

### Tool 4: compare_price (Stretch)

**What it does:**
Given an item, finds similar listings in the dataset and reports whether the price is above, below, or at the average for comparable items.

**Input parameters:**
- `item` (dict): The listing dict to evaluate

**What it returns:**
A string like "This is priced $5 below average for similar vintage tees ($27 avg from 4 comparable listings)."

**What happens if it fails or returns nothing:**
If fewer than 2 comparable listings exist, returns "Not enough similar listings to compare price."

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop is a sequential pipeline with conditional early exit:

1. **Parse query**: Extract description, size, and max_price from the user's natural language query using regex pattern matching (look for "size [X]", "under $[N]", "$[N]" patterns; everything else is description).
2. **Call search_listings** with parsed params. Check result:
   - If `results == []`: set `session["error"]` with a helpful message. **Return early** — do not call subsequent tools.
   - If results exist: set `session["selected_item"] = results[0]` and continue.
3. **Call suggest_outfit** with selected_item and wardrobe. Store result in `session["outfit_suggestion"]`.
4. **Call create_fit_card** with outfit_suggestion and selected_item. Store result in `session["fit_card"]`.
5. **Return session** — the interaction is complete.

The loop is not purely fixed-sequence because it branches at step 2: the agent's behavior changes based on search results. The key conditional: "if no results, stop and inform the user."

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dictionary is the source of truth for the entire interaction. It is initialized at the start of `run_agent()` and threaded through each tool call:

- `session["query"]` — original user input (immutable)
- `session["parsed"]` — extracted description/size/max_price dict
- `session["search_results"]` — full list from search_listings
- `session["selected_item"]` — `search_results[0]`, passed to suggest_outfit and create_fit_card
- `session["wardrobe"]` — the user's wardrobe dict, passed to suggest_outfit
- `session["outfit_suggestion"]` — string from suggest_outfit, passed to create_fit_card
- `session["fit_card"]` — final output string
- `session["error"]` — set only if the interaction terminated early; None on success

Each tool receives its inputs directly from the session dict. No tool reads from a global or re-asks the user.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Agent tells the user: "No listings found matching '[description]'. Try removing the size filter, raising your budget, or using different keywords." Does NOT proceed to suggest_outfit. |
| suggest_outfit | Wardrobe is empty | Tool provides general styling advice for the item (e.g., "This vintage graphic tee has a grunge vibe — pair with wide-leg jeans, chunky boots, and layered jewelry"). Agent continues to create_fit_card normally. |
| create_fit_card | Outfit input is missing or empty string | Tool returns an error message: "Could not generate a fit card — no outfit suggestion was provided." Agent stores this in session["fit_card"] and returns. |

---

## Architecture

```
User query
    |
    v
+-------------------+
| run_agent()       |
| (Planning Loop)   |
+-------------------+
    |
    | Step 1: Parse query (regex)
    v
session["parsed"] = {description, size, max_price}
    |
    | Step 2: search_listings(description, size, max_price)
    v
+--[results == []]?--+
|  YES               |  NO
|  session["error"]  |  session["selected_item"] = results[0]
|  RETURN EARLY      |
|                    v
|    Step 3: suggest_outfit(selected_item, wardrobe)
|                    |
|                    v
|    session["outfit_suggestion"] = "..."
|                    |
|    Step 4: create_fit_card(outfit_suggestion, selected_item)
|                    |
|                    v
|    session["fit_card"] = "..."
|                    |
+--------------------+
         |
         v
    Return session → UI displays results
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For search_listings: I'll give Claude the Tool 1 spec block (inputs, return type, failure mode, the TODO steps from tools.py) and the listing data structure (fields available). I'll ask it to implement the function using load_listings(). Before running, I'll verify: (1) it filters by all three params, (2) scoring uses keyword overlap with title + description + style_tags, (3) it returns [] on no matches without exceptions. I'll test with 3 queries: one that matches multiple items, one with size filter, one impossible query.

For suggest_outfit: I'll give Claude the Tool 2 spec plus the wardrobe schema structure. I'll ask it to implement using Groq's llama-3.3-70b-versatile. Before running, I'll verify it checks wardrobe['items'] emptiness and has two distinct prompt paths. I'll test with example wardrobe and empty wardrobe.

For create_fit_card: I'll give Claude the Tool 3 spec. I'll ask it to use temperature=0.9 for variety. I'll verify it guards against empty outfit string before calling the LLM. I'll run it 3 times on the same input to confirm outputs vary.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the full Architecture diagram, Planning Loop section, and State Management section from this planning.md. I'll ask it to implement run_agent() following the numbered steps already in agent.py. Before running, I'll verify: (1) it branches on empty search results, (2) it stores each result in the session dict, (3) it never calls suggest_outfit when results are empty. I'll test with both the happy path and the no-results path from the CLI test cases.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query: description="vintage graphic tee", size=None (no size mentioned), max_price=30.0 (extracted from "under $30"). The wardrobe context ("baggy jeans and chunky sneakers") is not used for search — it's already in the user's wardrobe data.

Calls: `search_listings("vintage graphic tee", size=None, max_price=30.0)`

Returns: A list of matching listings, e.g., [{"title": "Y2K Baby Tee — Butterfly Print", "price": 18.00, "platform": "depop", ...}, ...]. The agent sets `session["selected_item"] = results[0]`.

**Step 2:**
Results are not empty, so the agent proceeds.

Calls: `suggest_outfit(session["selected_item"], session["wardrobe"])`

The LLM receives the item details and the user's wardrobe items. It returns something like: "Pair this Y2K butterfly tee with your baggy straight-leg jeans for a casual 2000s throwback. Add your chunky white sneakers and keep accessories minimal — a simple chain necklace would complete the look. For a layered option, throw your oversized grey crewneck over it with the collar peeking out."

Stored in `session["outfit_suggestion"]`.

**Step 3:**
Calls: `create_fit_card(session["outfit_suggestion"], session["selected_item"])`

The LLM generates a shareable caption like: "found this y2k butterfly tee on depop for $18 and it goes stupid hard with my baggy jeans. giving early 2000s mall rat energy and i'm here for it"

Stored in `session["fit_card"]`.

**Final output to user:**
The UI shows three panels:
1. **Top listing**: "Y2K Baby Tee — Butterfly Print | $18.00 | depop | Excellent condition | Size: S/M"
2. **Outfit idea**: The full suggestion text from step 2
3. **Fit card**: The shareable caption from step 3
