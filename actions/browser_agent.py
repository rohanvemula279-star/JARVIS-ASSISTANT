from actions.browser_navigation import navigate
from actions.browser_interaction import interact
from actions.browser_extraction import extract
from actions.browser_research import research
from actions.browser_core import BrowserEngine
import google.generativeai as genai
from memory.config_manager import get_gemini_key
import json
import os
import asyncio


_gemini_model = None

def _get_planner_model():
    global _gemini_model
    if _gemini_model is None:
        genai.configure(api_key=get_gemini_key())
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


BROWSER_AGENT_PROMPT = """You are a browser automation agent. You control a real browser on the user's Windows laptop.

Given a user request, you produce a JSON plan: a list of steps to execute.

AVAILABLE ACTIONS:

NAVIGATION (module: "nav"):
  open_url(url), search(query, engine_name="google"|"youtube"|"amazon"|"flipkart"),
  go_back(), go_forward(), reload(), stop_loading(),
  open_link_new_tab(url), open_link_background_tab(url), new_blank_tab(),
  close_current_tab(), close_tab_by_title(title), switch_tab(title|tab_id),
  duplicate_tab(), pin_tab()

INTERACTION (module: "act"):
  click(selector|text), double_click(selector|text), right_click(selector|text),
  scroll_to_top(), scroll_to_bottom(), scroll_by(pixels, direction="down"|"up"),
  scroll_container(selector, pixels), hover(selector|text), focus(selector),
  type_text(selector, text, delay=50), fill_text(selector, text), clear_input(selector),
  select_dropdown(selector, value|label), check_checkbox(selector|text),
  uncheck_checkbox(selector|text), click_radio(selector|text),
  press_key(key), drag_and_drop(source_selector, target_selector),
  upload_file(selector, file_path), submit_form(selector), close_popup(selector)

EXTRACTION (module: "ext"):
  get_text(), get_html(), get_element_text(selector), get_attribute(selector, attribute),
  is_visible(selector), is_enabled(selector), get_title(), get_url(),
  extract_links(), extract_images(), extract_tables(), extract_forms(),
  summarize_page(), summarize_section(selector|text), classify_page()

RESEARCH (module: "res"):
  web_search(query), open_top_results(query, count=3), summarize_all_tabs(),
  compare_tabs(tab_ids, criterion), aggregate_tabs(question),
  extract_facts(facts=[...]), rank_items(criterion), answer_from_page(question),
  deep_research(topic, depth=2), should_continue_browsing(question),
  save_research_session(name), generate_report(topic),
  detect_duplicate_tabs(), group_tabs(), name_tab_groups(),
  fill_login(username, password), fill_signup(data), fill_checkout(data),
  select_variant(variant_type, value), add_to_cart(), remove_from_cart(item_name),
  proceed_checkout(), compare_prices(), book_reservation(data),
  fill_form_smart(data), accept_cookies(), confirm_before_purchase(description),
  take_snapshot(name), get_action_history(last_n), activity_summary()

RULES:
1. Output ONLY valid JSON array of steps
2. Each step: {"module": "nav"|"act"|"ext"|"res", "action": "action_name", "params": {...}}
3. For YouTube: use search(query, engine_name="youtube") then click the first video
4. For purchases: ALWAYS include confirm_before_purchase before final payment
5. Use wait steps between page loads: {"module": "wait", "action": "wait", "params": {"seconds": 2}}
6. If you need to read the page to decide next steps, add a step with module "ext" action "get_text" or "summarize_page", then mark "needs_replanning": true
7. Keep plans SHORT. Minimum steps to accomplish the task.
8. For Amazon India use amazon.in, for flights use google.com/travel

Example - "Play Naa Ready on YouTube":
[
  {"module": "nav", "action": "search", "params": {"query": "Naa Ready", "engine_name": "youtube"}},
  {"module": "wait", "action": "wait", "params": {"seconds": 3}},
  {"module": "act", "action": "click", "params": {"selector": "ytd-video-renderer a#video-title"}}
]

Example - "Add iPhone to cart on Amazon":
[
  {"module": "nav", "action": "search", "params": {"query": "iPhone 15", "engine_name": "amazon"}},
  {"module": "wait", "action": "wait", "params": {"seconds": 3}},
  {"module": "act", "action": "click", "params": {"selector": "div.s-result-item h2 a"}},
  {"module": "wait", "action": "wait", "params": {"seconds": 3}},
  {"module": "res", "action": "add_to_cart", "params": {}},
  {"module": "res", "action": "confirm_before_purchase", "params": {"description": "Add iPhone 15 to Amazon cart"}}
]
"""


async def execute_browser_task(user_request: str, user_data: dict = None) -> str:
    """
    Main entry point. Called by your assistant when user wants browser action.
    
    user_request: natural language like "play a song on YouTube" or "book flight to Tirupati"
    user_data: optional dict with user info for forms (name, email, phone, address, etc.)
    """
    model = _get_planner_model()
    
    # Get current browser state for context
    engine = await BrowserEngine.get_instance()
    current_url = engine.get_active_page().url if engine.get_active_page() else "about:blank"
    current_title = await engine.get_active_page().title() if engine.get_active_page() else ""
    tab_count = len(engine.pages)
    
    context = f"""Current browser state:
- Active tab: {current_title} ({current_url})
- Open tabs: {tab_count}
- User data available: {list(user_data.keys()) if user_data else 'none'}

User request: {user_request}"""
    
    # Generate plan
    response = model.generate_content(
        BROWSER_AGENT_PROMPT + "\n\n" + context,
        generation_config=genai.GenerationConfig(
            max_output_tokens=1000,
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    
    try:
        plan = json.loads(response.text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        text = response.text
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            plan = json.loads(text[start:end])
        else:
            return f"Failed to generate plan. Raw response: {text[:500]}"
    
    # Execute plan step by step
    results = []
    for i, step in enumerate(plan):
        module = step.get("module")
        action = step.get("action")
        params = step.get("params", {})
        
        # Inject user_data into form-filling params if needed
        if user_data and "data" in params and params["data"] is None:
            params["data"] = user_data
        
        try:
            if module == "nav":
                result = await navigate(action, **params)
            elif module == "act":
                result = await interact(action, **params)
            elif module == "ext":
                result = await extract(action, **params)
            elif module == "res":
                result = await research(action, **params)
            elif module == "wait":
                seconds = params.get("seconds", 2)
                await asyncio.sleep(seconds)
                result = f"Waited {seconds}s"
            else:
                result = f"Unknown module: {module}"
            
            results.append({"step": i, "action": f"{module}.{action}", "result": str(result)[:300]})
            
            # Check if this is a confirmation request
            if "CONFIRMATION_REQUIRED" in str(result):
                return result  # Return to user for confirmation
            
            # Check if replanning is needed
            if step.get("needs_replanning"):
                # Re-plan with new context (page content)
                return await execute_browser_task(
                    f"{user_request}\n\nProgress so far: {json.dumps(results)}\n\nCurrent page content: {result[:2000]}",
                    user_data
                )
                
        except Exception as e:
            results.append({"step": i, "action": f"{module}.{action}", "error": str(e)})
            # Don't stop on error — try next step
            continue
    
    # Return summary
    final_result = results[-1] if results else {"result": "No steps executed"}
    return json.dumps({
        "status": "completed",
        "steps_executed": len(results),
        "final_result": final_result,
        "all_results": results
    }, indent=2)


async def shutdown_browser():
    """Cleanly close the browser."""
    engine = await BrowserEngine.get_instance()
    await engine.shutdown()
