# FitFindr

A multi-tool AI agent that helps users find secondhand clothing pieces and figure out how to wear them. The agent searches listings, suggests outfits based on an existing wardrobe, and generates shareable fit cards.

## Tool Inventory

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `search_listings` | `description` (str), `size` (str\|None), `max_price` (float\|None) | list[dict] — matching listings sorted by relevance | Search mock dataset for items matching keywords, size, and price constraints |
| `suggest_outfit` | `new_item` (dict), `wardrobe` (dict) | str — 1-2 outfit suggestions | Use LLM to suggest complete outfits combining the new item with existing wardrobe pieces |
| `create_fit_card` | `outfit` (str), `new_item` (dict) | str — shareable caption | Generate an Instagram/TikTok-style caption for the outfit |

## How the Planning Loop Works

The planning loop in `agent.py` follows a sequential pipeline with conditional early exit:

1. **Parse**: Extract `description`, `size`, and `max_price` from the natural language query using regex (detects "under $X", "size X" patterns, strips filler phrases).
2. **Search**: Call `search_listings()` with parsed params.
   - **If results are empty**: Set `session["error"]` with an actionable message telling the user what to adjust. **Return immediately** — do not call downstream tools.
   - **If results exist**: Select `results[0]` as the item to style.
3. **Suggest**: Call `suggest_outfit()` with the selected item and user's wardrobe.
4. **Fit Card**: Call `create_fit_card()` with the outfit suggestion and selected item.
5. **Return**: The completed session dict flows to the UI.

The agent's behavior changes based on what it receives — it does not blindly execute all three tools in sequence.

## State Management

A single `session` dictionary is initialized at the start of each interaction and passed through the pipeline:

- `session["parsed"]` — extracted query parameters (used by search)
- `session["search_results"]` — full results list from search_listings
- `session["selected_item"]` — top result, passed to suggest_outfit and create_fit_card
- `session["wardrobe"]` — user's wardrobe, passed to suggest_outfit
- `session["outfit_suggestion"]` — LLM output from suggest_outfit, passed to create_fit_card
- `session["fit_card"]` — final caption output
- `session["error"]` — set only on early termination; None on success

Each tool receives inputs directly from the session — no re-prompting, no globals.

## Error Handling

| Tool | Failure Mode | What Happens |
|------|-------------|--------------|
| `search_listings` | No results match | Returns `[]`. Agent sets `session["error"]` = "No listings found matching 'X'. Try broadening your search — remove the size filter, increase your budget, or use different keywords." Stops early. |
| `suggest_outfit` | Empty wardrobe | Tool detects empty `wardrobe["items"]` and sends an alternate prompt asking for general styling advice. Returns useful output — the flow continues normally. |
| `suggest_outfit` | LLM API failure | Catches exception, returns fallback: "Could not generate outfit suggestions right now. This [category] would pair well with neutral basics and layering pieces." |
| `create_fit_card` | Empty/whitespace outfit string | Returns error message immediately without calling LLM: "Could not generate a fit card — no outfit suggestion was provided." |
| `create_fit_card` | LLM API failure | Catches exception, returns a simple fallback caption built from item title/price/platform. |

**Example from testing**: Running `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`. The agent responds: "No listings found matching 'designer ballgown', size XXS, under $5. Try broadening your search — remove the size filter, increase your budget, or use different keywords."

## Spec Reflection

**One way the spec helped**: Defining the exact error handling responses in planning.md before coding meant I didn't have to make UX decisions while implementing. The conditional branch logic was already decided — I just translated it to code.

**One way implementation diverged**: The query parser in planning.md was described as "regex pattern matching" but in practice needed multiple passes — one for price, one for size, then stripping filler phrases from what remained to get the description. The single-pass approach implied by the spec wasn't sufficient for natural language queries.

## AI Usage

**Instance 1 — Tool implementation**: I provided Claude with the Tool 1-3 spec blocks from planning.md (inputs, return values, failure modes, TODO steps) plus the data_loader utility functions. Claude generated the three tool implementations. I revised the `search_listings` scoring to search across title + description + style_tags + category + colors + brand (the initial version only searched title). I also added explicit `try/except` blocks around LLM calls with meaningful fallback strings.

**Instance 2 — Planning loop**: I gave Claude the Architecture diagram, Planning Loop section, and State Management section from planning.md along with the session dict structure from agent.py. It produced the `run_agent()` implementation. I added the `_parse_query()` helper separately because the generated version tried to use the LLM for parsing (unnecessary overhead for structured patterns). I wrote the regex parsing myself to keep it fast and deterministic.

## Running the App

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
# Add your GROQ_API_KEY to .env
python app.py
```

Open the URL shown in terminal (usually http://localhost:7860).

## Running Tests

```bash
pytest tests/ -v
```
