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
Loads all listings from `listings.json` via `load_listings()` and filters them against the user's query. Matches are scored by how many of the listing's `title`, `description`, and `style_tags` fields contain keywords from `description`; results are returned ordered by match score (highest first).

**Input parameters:**
- `description` (str): Free-text query describing the item type and style (e.g., `"vintage graphic tee"`). Matched case-insensitively against each listing's `title`, `description`, and each entry in `style_tags`. A listing must match at least one keyword to be included.
- `size` (str, optional, default `None`): The user's size string (e.g., `"M"`, `"W30"`). When provided, only listings whose `size` field contains this string (case-insensitive substring match) are returned. When `None`, no size filter is applied.
- `max_price` (float, optional, default `None`): Upper price bound, inclusive. Only listings with `price <= max_price` are returned. When `None`, no price filter is applied.

**What it returns:**
A list of listing dicts ordered by relevance score (descending). Each dict contains exactly these fields:
- `id` (str): Unique listing identifier, e.g. `"lst_006"`
- `title` (str): Human-readable name, e.g. `"Graphic Tee — 2003 Tour Bootleg Style"`
- `description` (str): Seller's item description
- `category` (str): One of `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]): Style descriptors, e.g. `["vintage", "grunge", "streetwear"]`
- `size` (str): Size as listed, e.g. `"L"` or `"W30 L30"`
- `condition` (str): One of `excellent`, `good`, `fair`
- `price` (float): Price in USD
- `colors` (list[str]): Colors present in the item, e.g. `["black"]`
- `brand` (str or None): Brand name if known, otherwise `null`
- `platform` (str): Marketplace where the item is listed — one of `depop`, `thredUp`, `poshmark`

Returns an empty list `[]` when no listings pass all active filters.

**What happens if it fails or returns nothing:**
If the returned list is empty, the agent sets `session["error"]` to: `"I couldn't find any '[description]' listings under $[max_price]. Try a higher budget or a more general style term (e.g., 'graphic tee' instead of 'vintage bootleg graphic tee')."` The agent returns this message to the user and stops — it does **not** call `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a new clothing item the agent has selected and the user's current wardrobe, scores each wardrobe item by counting overlapping `style_tags` and compatible `colors` with the new item, then returns the top 2–3 highest-scoring pieces that cover distinct categories (e.g., one bottom, one shoe, one optional outer layer), plus a one-sentence styling note.

**Input parameters:**
- `new_item` (dict): A listing dict exactly as returned by `search_listings`. The tool reads `category`, `colors`, and `style_tags` from this dict to score compatibility. Must not be `None`.
- `wardrobe` (dict): A wardrobe dict with one key `"items"` whose value is a list of wardrobe item dicts. Each wardrobe item contains: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or None). Typically loaded via `get_example_wardrobe()`.

**What it returns:**
A dict with two keys:
- `"outfit"` (list[dict]): 2–3 wardrobe item dicts selected as the best pairing. Each dict contains: `id`, `name`, `category`, `colors`, `style_tags`, `notes`. The list covers distinct categories — the tool picks at most one item per category (e.g., one bottom + one shoe, not two bottoms). Empty list `[]` if wardrobe has no items.
- `"styling_note"` (str): A single sentence tip on how to wear the combination, e.g. `"Tuck the tee loosely into the jeans and let the jacket hang open for a relaxed streetwear silhouette."` Empty string `""` if wardrobe is empty.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is an empty list, the tool returns `{"outfit": [], "styling_note": ""}`. The agent checks this condition, sets `session["error"]` to: `"I found a great pick — [title] for $[price] on [platform] — but your wardrobe is empty so I can't suggest how to style it. Add a few basics (jeans, sneakers, a jacket) and try again."` The agent returns this message and stops — it does **not** call `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
Formats a selected listing and a suggested outfit into a structured fit card dict that the Gradio UI can render. Performs no filtering or scoring logic — it is purely a formatting function.

**Input parameters:**
- `listing` (dict): The selected listing dict from `search_listings`. Required fields: `title` (str), `price` (float), `platform` (str), `condition` (str), `colors` (list[str]), `brand` (str or None). Must not be `None`.
- `outfit` (list[dict]): The outfit list from `suggest_outfit`, containing 2–3 wardrobe item dicts each with `name` (str) and `category` (str). Must not be empty.
- `styling_note` (str): The styling tip string from `suggest_outfit`. May be empty string but not `None`.

**What it returns:**
A dict with four keys, or `None` if inputs are invalid (see failure case):
- `"header"` (str): `"{title} — ${price:.2f}"`, e.g. `"Graphic Tee — 2003 Tour Bootleg Style — $24.00"`
- `"source"` (str): `"Found on {platform} | Condition: {condition}"`, e.g. `"Found on depop | Condition: good"`
- `"outfit_lines"` (list[str]): One formatted string per outfit piece: `"{Category}: {name}"`, e.g. `["Bottoms: Baggy straight-leg jeans, dark wash", "Shoes: Chunky white sneakers"]`
- `"styling_note"` (str): The `styling_note` value passed in, unchanged.

**What happens if it fails or returns nothing:**
If `listing` is `None`, any required field on `listing` is missing, or `outfit` is an empty list, the tool returns `None`. The agent checks for `None`, sets `session["error"]` to: `"I ran into a problem putting together your fit card — some details are missing. Try starting over with a new search query."` and returns that message to the user.

---

### Additional Tools (if any)

None required beyond the three above.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs as a linear pipeline with an explicit early-exit check after every tool call. Here is the exact branching logic:

**Step 0 — Initialize session:**
At the start of each user turn, set:
```
session["wardrobe"] = get_example_wardrobe()   # or user-provided wardrobe
session["error"] = None
```

**Step 1 — Parse user input:**
Extract `description` (str, required), `size` (str or None), and `max_price` (float or None) from the user's message. Store as `session["query"] = {"description": ..., "size": ..., "max_price": ...}`.

**Step 2 — Call search_listings:**
```
results = search_listings(description, size, max_price)
```
- If `results == []`: set `session["error"]` to the no-results message, return the error string to the user. **STOP.**
- If `results` is non-empty: set `session["selected_item"] = results[0]` and continue.

**Step 3 — Call suggest_outfit:**
```
outfit_result = suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])
```
- If `outfit_result["outfit"] == []`: set `session["error"]` to the empty-wardrobe message, return it. **STOP.**
- If non-empty: set `session["outfit"] = outfit_result["outfit"]` and `session["styling_note"] = outfit_result["styling_note"]` and continue.

**Step 4 — Call create_fit_card:**
```
fit_card = create_fit_card(listing=session["selected_item"], outfit=session["outfit"], styling_note=session["styling_note"])
```
- If `fit_card is None`: set `session["error"]` to the incomplete-data message, return it. **STOP.**
- If non-None: set `session["fit_card"] = fit_card` and continue.

**Step 5 — Return result:**
Render `session["fit_card"]` into a formatted response string and return it to the user. The loop is done.

---

## State Management

**How does information from one tool get passed to the next?**

The agent maintains a single `session` dict initialized at the start of each user turn and passed by reference into each tool call handler. No tool reads from `session` directly — the planning loop reads from it and passes the relevant values as explicit arguments. Here are all keys written and read across the pipeline:

| Key | Type | Written after | Read by |
|-----|------|--------------|---------|
| `session["query"]` | dict (`description`, `size`, `max_price`) | Step 1 parse | Step 2 to build tool call |
| `session["wardrobe"]` | dict (wardrobe with `items` list) | Step 0 init | Step 3 to pass to suggest_outfit |
| `session["selected_item"]` | dict (full listing) | Step 2 (search_listings returns) | Steps 3 and 4 |
| `session["outfit"]` | list[dict] | Step 3 (suggest_outfit returns) | Step 4 |
| `session["styling_note"]` | str | Step 3 (suggest_outfit returns) | Step 4 |
| `session["fit_card"]` | dict | Step 4 (create_fit_card returns) | Step 5 to render final output |
| `session["error"]` | str or None | Any step on early exit | Step 5 to decide what to show user |

The session dict is initialized fresh each turn so state does not leak between separate user queries.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings pass all active filters (empty list returned) | "I couldn't find any '[description]' listings under $[max_price]. Try a higher budget (e.g., $50) or a more general style term like 'graphic tee' instead of '[original description]'." Agent stops here — does not call suggest_outfit or create_fit_card. |
| suggest_outfit | `wardrobe["items"]` is an empty list | "I found a great pick — [title] for $[price] on [platform] — but your wardrobe is empty so I can't suggest how to style it. Add a few basics (jeans, sneakers, a jacket) and try again." Agent stops here — does not call create_fit_card. |
| create_fit_card | `listing` is None / missing required fields, or `outfit` is an empty list | "I ran into a problem putting together your fit card — some details are missing. Try starting over with a new search query." Agent returns this message and stops. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                              │
│  "vintage graphic tee under $30, I wear baggy jeans"           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Planning Loop                              │
│  1. Parse: description, size, max_price from user message       │
│  2. Call search_listings → check results                        │
│  3. Call suggest_outfit → check outfit                          │
│  4. Call create_fit_card → check fit_card                       │
│  5. Render and return fit_card to user                          │
└──┬─────────────┬──────────────┬─────────────┬───────────────────┘
   │             │              │             │
   │ writes/reads│              │             │
   ▼             ▼              ▼             ▼
┌──────────────────────────────────────────────────────────────┐
│                     Session State (dict)                     │
│  query, wardrobe, selected_item, outfit, styling_note,       │
│  fit_card, error                                             │
└──────────────────────────────────────────────────────────────┘
   │                  │                  │
   ▼                  ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│search_listings│ │suggest_outfit│ │create_fit_card│
│              │ │              │ │              │
│ inputs:      │ │ inputs:      │ │ inputs:      │
│ description  │ │ new_item     │ │ listing      │
│ size         │ │ wardrobe     │ │ outfit       │
│ max_price    │ │              │ │ styling_note │
│              │ │ returns:     │ │              │
│ returns:     │ │ outfit[]     │ │ returns:     │
│ list[dict]   │ │ styling_note │ │ fit_card dict│
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
  results==[]?     outfit==[]?      card is None?
       │ YES            │ YES            │ YES
       ▼                ▼                ▼
  ┌─────────┐      ┌─────────┐      ┌─────────┐
  │  ERROR  │      │  ERROR  │      │  ERROR  │
  │ "no     │      │ "wardrobe│     │ "missing │
  │listings"│      │ empty"  │      │ data"   │
  │  STOP   │      │  STOP   │      │  STOP   │
  └─────────┘      └─────────┘      └─────────┘
       │ NO             │ NO             │ NO
       │                │                │
       └──────────────► └──────────────► └──────────────►
                                                          ▼
                                                   ┌───────────┐
                                                   │  Output   │
                                                   │ Fit card  │
                                                   │ to user   │
                                                   └───────────┘
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**search_listings:** I'll give Claude the Tool 1 block from planning.md (the description, all three parameters with types and semantics, the exact return value field list, and the empty-results failure behavior) plus a note to use `load_listings()` from `utils/data_loader.py`. I'll ask it to implement case-insensitive substring matching across `title`, `description`, and `style_tags`, with optional `size` and `max_price` filters, and to sort results by match score (count of keyword hits). Before accepting the output I'll check: (1) it imports `load_listings` not `open()`, (2) all three filters work independently (no filter should silently ignore None), (3) it returns `[]` not `None` on no match. I'll test with three queries: `("vintage graphic tee", None, 30.0)` expecting lst_006, `("formal blazer", None, 10.0)` expecting `[]`, and `("vintage", "M", None)` expecting only size-M listings.

**suggest_outfit:** I'll give Claude the Tool 2 block (inputs with field-level detail, the return dict shape with `outfit` list and `styling_note`, and the empty-wardrobe case). I'll ask for a scoring approach: for each wardrobe item, count overlapping strings between the item's `style_tags` and `new_item["style_tags"]`; pick the top-scoring item per category (at most 3 categories); return a short templated styling_note. I'll verify: (1) no crash when `wardrobe["items"] == []`, (2) the returned `outfit` list items are full dicts (not just ids), (3) no two returned items share the same `category`. I'll test with the example wardrobe and lst_006 (black vintage tee) and confirm the top picks include jeans and sneakers.

**create_fit_card:** I'll give Claude the Tool 3 block only (inputs, the four output keys with their exact string formats, and the None-return failure case). I'll ask for a pure formatting function — no filtering logic. I'll check: (1) all four output keys are always present when inputs are valid, (2) `outfit_lines` capitalizes the category, (3) the function returns `None` (not raises) when `listing` is None or `outfit` is `[]`. I'll test with one valid call and two invalid calls (None listing, empty outfit list).

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop section, the State Management table, and the Architecture diagram from planning.md. I'll ask it to implement a single `run_agent(user_message: str, session: dict) -> str` function that: (1) calls the three tools in order, (2) checks each early-exit condition exactly as described, (3) mutates `session` in-place so state persists across Gradio calls. I'll verify the output by tracing two paths manually in a Python REPL: the happy path (query matching at least one listing + non-empty example wardrobe → returns a rendered fit card string) and a no-match path (query matching zero listings → returns error string and `session["selected_item"]` is never set). I'll also confirm that calling `run_agent` twice in a row does not bleed state from the first call into the second.

---

## What FitFindr Does

FitFindr is an AI shopping assistant that helps users find secondhand clothing that fits their style and budget, then shows them how to wear it with what they already own. A user describes what they're looking for (e.g., "vintage graphic tee under $30, I wear baggy jeans") and the agent calls `search_listings` to filter the mock dataset, then `suggest_outfit` to combine the best match with the user's wardrobe, and finally `create_fit_card` to package the result into a shareable look. If a tool returns nothing — no listings match, the wardrobe is empty, or the outfit data is incomplete — the agent surfaces a clear, specific message rather than silently failing or hallucinating a result.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse and call search_listings:**
The agent extracts `description="vintage graphic tee"`, `size=None` (not specified), `max_price=30.0` from the user's message and calls `search_listings("vintage graphic tee", None, 30.0)`. The tool loads all listings, scores each by keyword overlap with "vintage", "graphic", "tee" across `title`, `description`, and `style_tags`, and filters to `price <= 30.0`. lst_006 ("Graphic Tee — 2003 Tour Bootleg Style", $24, tags: `["graphic tee", "vintage", "grunge", "streetwear"]`) scores highest and is returned as `results[0]`. The agent sets `session["selected_item"] = results[0]`.

**Step 2 — Call suggest_outfit:**
The agent calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. The tool scores wardrobe items by counting shared `style_tags` with lst_006's tags (`["graphic tee", "vintage", "grunge", "streetwear"]`). Top matches:
- w_001 "Baggy straight-leg jeans, dark wash" — tags `["denim", "streetwear", "baggy"]` → 1 overlap (streetwear), category: bottoms ✓
- w_007 "Chunky white sneakers" — tags `["sneakers", "chunky", "streetwear"]` → 1 overlap, category: shoes ✓
- w_006 "Vintage black denim jacket" — tags `["denim", "vintage", "classic"]` → 1 overlap (vintage), category: outerwear ✓

The tool returns `{"outfit": [w_001, w_007, w_006], "styling_note": "Tuck the tee loosely into the jeans and let the jacket hang open for a relaxed streetwear silhouette."}`. The agent stores both values in session.

**Step 3 — Call create_fit_card:**
The agent calls `create_fit_card(listing=session["selected_item"], outfit=session["outfit"], styling_note=session["styling_note"])`. The tool formats:
- `header`: `"Graphic Tee — 2003 Tour Bootleg Style — $24.00"`
- `source`: `"Found on depop | Condition: good"`
- `outfit_lines`: `["Bottoms: Baggy straight-leg jeans, dark wash", "Shoes: Chunky white sneakers", "Outerwear: Vintage black denim jacket"]`
- `styling_note`: `"Tuck the tee loosely into the jeans and let the jacket hang open for a relaxed streetwear silhouette."`

The agent stores the result in `session["fit_card"]`.

**Final output to user:**
```
Graphic Tee — 2003 Tour Bootleg Style — $24.00
Found on depop | Condition: good

Style it with:
  Bottoms: Baggy straight-leg jeans, dark wash
  Shoes: Chunky white sneakers
  Outerwear: Vintage black denim jacket

Styling tip: Tuck the tee loosely into the jeans and let the jacket hang open for a relaxed streetwear silhouette.
```

**Error path (if Step 1 returned empty results):**
The agent would respond: "I couldn't find any 'vintage graphic tee' listings under $30. Try a higher budget (e.g., $50) or a more general style term like 'graphic tee' instead of 'vintage graphic tee'." — and stop without calling the remaining tools.
