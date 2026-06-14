"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


WARDROBE_EXAMPLE = "Example wardrobe"
WARDROBE_EMPTY = "Empty wardrobe (new user)"

# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either WARDROBE_EXAMPLE or WARDROBE_EMPTY.

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)
        Each string maps to one of the three output panels in the UI.

    """
    # Step 1: Guard against empty query
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", ""

    # Step 2: Select wardrobe based on radio choice
    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == WARDROBE_EXAMPLE
        else get_empty_wardrobe()
    )

    # Step 3: Run the agent planning loop
    session = run_agent(query=user_query, wardrobe=wardrobe)

    # Step 4: If the agent hit an error, surface it in the first panel only
    if session["error"]:
        return session["error"], "", ""

    # Step 5: Format the selected listing into a readable panel string
    item = session["selected_item"]
    brand_line = f"Brand: {item['brand']}\n" if item.get("brand") else ""
    listing_text = (
        f"{item['title']}\n\n"
        f"Price:     ${item['price']:.2f}\n"
        f"Platform:  {item['platform']}\n"
        f"Condition: {item['condition']}\n"
        f"Size:      {item['size']}\n"
        f"Colors:    {', '.join(item['colors'])}\n"
        f"{brand_line}"
        f"Tags:      {', '.join(item['style_tags'])}\n\n"
        f"{item['description']}"
    )

    return listing_text, session["outfit_suggestion"], session["fit_card"]


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=[WARDROBE_EXAMPLE, WARDROBE_EMPTY],
                value=WARDROBE_EXAMPLE,
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, WARDROBE_EXAMPLE] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
