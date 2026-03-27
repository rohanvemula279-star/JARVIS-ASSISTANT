from actions.browser_core import BrowserEngine
from actions.browser_navigation import navigate
from actions.browser_interaction import interact
from actions.browser_extraction import extract, _get_text, _get_gemini
import google.generativeai as genai
import json
import asyncio


async def research(action: str, **params) -> str:
    """Router for research, task, and session actions."""
    engine = await BrowserEngine.get_instance()
    
    handlers = {
        # Search & Research
        "web_search": _web_search,
        "open_top_results": _open_top_results,
        "summarize_all_tabs": _summarize_all_tabs,
        "compare_tabs": _compare_tabs,
        "aggregate_tabs": _aggregate_tabs,
        "extract_facts": _extract_facts,
        "rank_items": _rank_items,
        "answer_from_page": _answer_from_page,
        "deep_research": _deep_research,
        "should_continue_browsing": _should_continue,
        "save_research_session": _save_research_session,
        "generate_report": _generate_report,
        "detect_duplicate_tabs": _detect_duplicate_tabs,
        "group_tabs": _group_tabs,
        "name_tab_groups": _name_tab_groups,
        
        # Forms & Transactions
        "fill_login": _fill_login,
        "fill_signup": _fill_signup,
        "fill_checkout": _fill_checkout,
        "select_variant": _select_variant,
        "add_to_cart": _add_to_cart,
        "remove_from_cart": _remove_from_cart,
        "proceed_checkout": _proceed_checkout,
        "compare_prices": _compare_prices,
        "book_reservation": _book_reservation,
        "fill_form_smart": _fill_form_smart,
        "accept_cookies": _accept_cookies,
        "confirm_before_purchase": _confirm_before_purchase,
        
        # Session & Memory
        "take_snapshot": _take_snapshot,
        "get_action_history": _get_action_history,
        "activity_summary": _activity_summary,
    }
    
    handler = handlers.get(action)
    if not handler:
        return f"Unknown research action: {action}"
    
    result = await handler(engine, **params)
    engine.log_action(action, params, str(result)[:200])
    return result


# ==================== SEARCH & RESEARCH ====================

async def _web_search(engine, query: str, **_) -> str:
    """Search Google and return results page."""
    return await navigate("search", query=query, engine_name="google")


async def _open_top_results(engine, query: str, count: int = 3, **_) -> str:
    """Search and open top N results in background tabs."""
    await navigate("search", query=query, engine_name="google")
    page = engine.get_active_page()
    await asyncio.sleep(2)
    
    # Extract search result links
    links = await page.evaluate(f"""
    () => Array.from(document.querySelectorAll('div.g a[href]'))
        .map(a => a.href)
        .filter(url => url.startsWith('http') && !url.includes('google.'))
        .slice(0, {count})
    """)
    
    opened = []
    for url in links:
        await navigate("open_link_background_tab", url=url)
        opened.append(url)
    
    return f"Opened {len(opened)} results in background tabs: {json.dumps(opened)}"


async def _summarize_all_tabs(engine, **_) -> str:
    """Read and summarize each open tab."""
    summaries = {}
    original_tab = engine.active_tab_id
    
    for tab_id, page in engine.pages.items():
        try:
            engine.active_tab_id = tab_id
            title = await page.title()
            text = await _get_text(engine)
            if len(text) > 100:
                model = _get_gemini()
                resp = model.generate_content(
                    f"Summarize in 2-3 sentences:\n\n{text[:3000]}",
                    generation_config=genai.GenerationConfig(max_output_tokens=150, temperature=0.3)
                )
                summaries[title] = resp.text
            else:
                summaries[title] = "(too little content)"
        except:
            summaries[tab_id] = "(error reading tab)"
    
    engine.active_tab_id = original_tab
    return json.dumps(summaries, indent=2)


async def _compare_tabs(engine, tab_ids: list = None, criterion: str = "", **_) -> str:
    """Compare content of multiple tabs side by side."""
    contents = {}
    tab_list = tab_ids or list(engine.pages.keys())
    
    for tab_id in tab_list[:5]:  # Max 5 tabs
        if tab_id in engine.pages:
            page = engine.pages[tab_id]
            engine.active_tab_id = tab_id
            title = await page.title()
            text = await _get_text(engine)
            contents[title] = text[:2000]
    
    combined = "\n\n---\n\n".join([f"**{t}**:\n{c}" for t, c in contents.items()])
    
    model = _get_gemini()
    prompt = f"Compare these pages{' based on: ' + criterion if criterion else ''}:\n\n{combined[:8000]}"
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(max_output_tokens=500, temperature=0.3)
    )
    return resp.text


async def _aggregate_tabs(engine, question: str = "summarize all information", **_) -> str:
    """Aggregate information from all tabs into a single answer."""
    all_text = []
    for tab_id, page in engine.pages.items():
        engine.active_tab_id = tab_id
        title = await page.title()
        text = await _get_text(engine)
        all_text.append(f"[{title}]: {text[:2000]}")
    
    combined = "\n\n".join(all_text)
    model = _get_gemini()
    resp = model.generate_content(
        f"Based on all these sources, {question}:\n\n{combined[:10000]}",
        generation_config=genai.GenerationConfig(max_output_tokens=600, temperature=0.3)
    )
    return resp.text


async def _extract_facts(engine, facts: list = None, **_) -> str:
    """Extract specific facts (prices, ratings, dates, names) from all tabs."""
    fact_types = facts or ["prices", "ratings", "dates", "names"]
    all_data = []
    
    for tab_id, page in engine.pages.items():
        engine.active_tab_id = tab_id
        title = await page.title()
        text = await _get_text(engine)
        all_data.append(f"[{title}]: {text[:2000]}")
    
    combined = "\n\n".join(all_data)
    model = _get_gemini()
    resp = model.generate_content(
        f"Extract these facts from the pages: {fact_types}. Return as JSON.\n\n{combined[:8000]}",
        generation_config=genai.GenerationConfig(max_output_tokens=500, temperature=0.1)
    )
    return resp.text


async def _rank_items(engine, criterion: str = "best value", **_) -> str:
    """Rank items across tabs based on a criterion."""
    all_data = []
    for tab_id, page in engine.pages.items():
        engine.active_tab_id = tab_id
        title = await page.title()
        text = await _get_text(engine)
        all_data.append(f"[{title}]: {text[:1500]}")
    
    combined = "\n\n".join(all_data)
    model = _get_gemini()
    resp = model.generate_content(
        f"Rank these items by '{criterion}'. Give a numbered list with reasons:\n\n{combined[:8000]}",
        generation_config=genai.GenerationConfig(max_output_tokens=400, temperature=0.3)
    )
    return resp.text


async def _answer_from_page(engine, question: str, **_) -> str:
    """Answer user question using current page content."""
    text = await _get_text(engine)
    model = _get_gemini()
    resp = model.generate_content(
        f"Answer this question using ONLY the page content below. If the answer isn't in the content, say so.\n\nQuestion: {question}\n\nPage content:\n{text[:5000]}",
        generation_config=genai.GenerationConfig(max_output_tokens=300, temperature=0.3)
    )
    return resp.text


async def _deep_research(engine, topic: str, depth: int = 2, **_) -> str:
    """Follow citations/links recursively to research a topic."""
    visited = set()
    findings = []
    
    # Initial search
    await _open_top_results(engine, query=topic, count=3)
    
    for _ in range(depth):
        for tab_id, page in list(engine.pages.items()):
            url = page.url
            if url in visited:
                continue
            visited.add(url)
            
            engine.active_tab_id = tab_id
            text = await _get_text(engine)
            title = await page.title()
            findings.append(f"[{title}] ({url}): {text[:1500]}")
    
    combined = "\n\n".join(findings)
    model = _get_gemini()
    resp = model.generate_content(
        f"Based on this research about '{topic}', provide a comprehensive summary with key findings:\n\n{combined[:10000]}",
        generation_config=genai.GenerationConfig(max_output_tokens=800, temperature=0.3)
    )
    return resp.text


async def _should_continue(engine, question: str, **_) -> str:
    """Detect if more browsing is needed or existing info is enough."""
    text = await _get_text(engine)
    model = _get_gemini()
    resp = model.generate_content(
        f"Given this question: '{question}'\nAnd this page content: {text[:3000]}\n\nIs the information sufficient to answer? Reply ONLY 'SUFFICIENT' or 'NEED_MORE_BROWSING' with a brief reason.",
        generation_config=genai.GenerationConfig(max_output_tokens=50, temperature=0.1)
    )
    return resp.text


async def _save_research_session(engine, name: str, **_) -> str:
    """Save current tab set as a named session."""
    session_data = {}
    for tab_id, page in engine.pages.items():
        session_data[tab_id] = {
            "url": page.url,
            "title": await page.title()
        }
    engine.sessions[name] = session_data
    return f"Session '{name}' saved with {len(session_data)} tabs"


async def _generate_report(engine, topic: str = "", **_) -> str:
    """Generate a structured report from all open tabs."""
    summaries = await _summarize_all_tabs(engine)
    model = _get_gemini()
    resp = model.generate_content(
        f"""Generate a structured report{' about ' + topic if topic else ''} from these tab summaries.
Format: Title, Executive Summary, Key Findings (bullets), Sources (URLs), Conclusion.

Tab summaries:
{summaries}""",
        generation_config=genai.GenerationConfig(max_output_tokens=800, temperature=0.3)
    )
    return resp.text


async def _detect_duplicate_tabs(engine, **_) -> str:
    """Find tabs with similar content."""
    tab_info = {}
    for tab_id, page in engine.pages.items():
        tab_info[tab_id] = {"url": page.url, "title": await page.title()}
    
    # Simple URL-domain based dedup
    from urllib.parse import urlparse
    domains = {}
    for tid, info in tab_info.items():
        domain = urlparse(info["url"]).netloc
        domains.setdefault(domain, []).append(tid)
    
    duplicates = {d: tids for d, tids in domains.items() if len(tids) > 1}
    return json.dumps({"potential_duplicates": duplicates, "all_tabs": tab_info}, indent=2)


async def _group_tabs(engine, **_) -> str:
    """Group tabs by topic automatically."""
    tab_info = []
    for tab_id, page in engine.pages.items():
        tab_info.append({"id": tab_id, "title": await page.title(), "url": page.url})
    
    model = _get_gemini()
    resp = model.generate_content(
        f"Group these browser tabs by topic. Return JSON with group names as keys and lists of tab IDs as values:\n\n{json.dumps(tab_info)}",
        generation_config=genai.GenerationConfig(max_output_tokens=300, temperature=0.2)
    )
    return resp.text


async def _name_tab_groups(engine, **_) -> str:
    return await _group_tabs(engine)


# ==================== FORMS & TRANSACTIONS ====================

async def _fill_login(engine, username: str, password: str, **_) -> str:
    """Detect and fill login form."""
    page = engine.get_active_page()
    
    # Try common login field selectors
    username_selectors = ['input[type="email"]', 'input[name="username"]', 'input[name="email"]',
                          'input[id="username"]', 'input[id="email"]', 'input[type="text"]']
    password_selectors = ['input[type="password"]']
    
    filled_user = False
    for sel in username_selectors:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, username)
                filled_user = True
                break
        except:
            continue
    
    filled_pass = False
    for sel in password_selectors:
        try:
            if await page.locator(sel).count() > 0:
                await page.fill(sel, password)
                filled_pass = True
                break
        except:
            continue
    
    if filled_user and filled_pass:
        return "Login form filled. Ready to submit."
    return f"Partially filled: username={'✓' if filled_user else '✗'}, password={'✓' if filled_pass else '✗'}"


async def _fill_signup(engine, data: dict, **_) -> str:
    """Fill signup form with provided data dict."""
    return await _fill_form_smart(engine, data=data)


async def _fill_checkout(engine, data: dict, **_) -> str:
    """Fill checkout form with shipping/billing data."""
    return await _fill_form_smart(engine, data=data)


async def _fill_form_smart(engine, data: dict = None, **_) -> str:
    """
    Intelligently fill any form by matching field names/labels to data keys.
    data example: {"name": "Rahul", "email": "r@g.com", "phone": "9876543210", "address": "..."}
    """
    if not data:
        return "No data provided to fill"
    
    page = engine.get_active_page()
    forms_json = await extract("extract_forms")
    forms = json.loads(forms_json)
    
    filled = []
    for form in forms:
        for field in form.get("fields", []):
            field_name = (field.get("name", "") + field.get("placeholder", "") + field.get("id", "")).lower()
            for key, value in data.items():
                if key.lower() in field_name or field_name in key.lower():
                    selector = f"#{field['id']}" if field.get("id") else f"[name='{field['name']}']"
                    try:
                        await page.fill(selector, str(value))
                        filled.append(f"{key}={value}")
                    except:
                        pass
    
    return f"Filled {len(filled)} fields: {', '.join(filled)}" if filled else "Could not match fields to data"


async def _select_variant(engine, variant_type: str, value: str, **_) -> str:
    """Select product variant (size, color) by clicking matching option."""
    page = engine.get_active_page()
    
    # Try clicking text that matches the value
    try:
        el = page.get_by_text(value, exact=False).first
        if await el.count() > 0:
            await el.click()
            return f"Selected {variant_type}: {value}"
    except:
        pass
    
    # Try dropdown
    try:
        dropdowns = await page.locator("select").all()
        for dd in dropdowns:
            options_text = await dd.inner_text()
            if value.lower() in options_text.lower():
                await dd.select_option(label=value)
                return f"Selected {variant_type}: {value} from dropdown"
    except:
        pass
    
    return f"Could not find variant option '{value}'"


async def _add_to_cart(engine, **_) -> str:
    """Click Add to Cart button."""
    page = engine.get_active_page()
    cart_texts = ["Add to Cart", "Add to Bag", "Buy Now", "Add to basket"]
    
    for text in cart_texts:
        try:
            el = page.get_by_role("button", name=text).first
            if await el.count() > 0:
                await el.click()
                await asyncio.sleep(2)
                return f"Clicked '{text}'"
        except:
            continue
    
    # Fallback: try by ID
    for sel in ["#add-to-cart-button", "#addToCart", ".add-to-cart"]:
        try:
            if await page.locator(sel).count() > 0:
                await page.click(sel)
                return f"Clicked add-to-cart via '{sel}'"
        except:
            continue
    
    return "Could not find Add to Cart button"


async def _remove_from_cart(engine, item_name: str = "", **_) -> str:
    """Remove item from cart."""
    page = engine.get_active_page()
    remove_texts = ["Remove", "Delete", "Remove from cart"]
    
    for text in remove_texts:
        try:
            el = page.get_by_role("button", name=text).first
            if await el.count() > 0:
                await el.click()
                return f"Removed item from cart"
        except:
            continue
    
    return "Could not find Remove button"


async def _proceed_checkout(engine, **_) -> str:
    """Click through checkout steps."""
    page = engine.get_active_page()
    checkout_texts = ["Proceed to Checkout", "Checkout", "Place Order", "Continue",
                      "Proceed to Buy", "Buy Now"]
    
    for text in checkout_texts:
        try:
            el = page.get_by_role("button", name=text).first
            if await el.count() > 0:
                await el.click()
                await asyncio.sleep(3)
                return f"Clicked '{text}'"
        except:
            try:
                el = page.get_by_role("link", name=text).first
                if await el.count() > 0:
                    await el.click()
                    await asyncio.sleep(3)
                    return f"Clicked '{text}' link"
            except:
                continue
    
    return "Could not find checkout button"


async def _compare_prices(engine, **_) -> str:
    """Compare final prices including fees/taxes across tabs."""
    return await _extract_facts(engine, facts=["price", "total", "tax", "shipping", "fees"])


async def _book_reservation(engine, data: dict = None, **_) -> str:
    """Fill reservation form (hotel, restaurant, flight)."""
    return await _fill_form_smart(engine, data=data)


async def _accept_cookies(engine, **_) -> str:
    """Close GDPR/cookie banners."""
    return await interact("close_popup")


async def _confirm_before_purchase(engine, description: str = "", **_) -> str:
    """
    CRITICAL: Returns confirmation request instead of executing.
    The agent MUST call this before any purchase/irreversible action.
    """
    page = engine.get_active_page()
    title = await page.title()
    url = page.url
    
    return json.dumps({
        "type": "CONFIRMATION_REQUIRED",
        "message": f"⚠️ About to proceed with: {description}",
        "page": title,
        "url": url,
        "instruction": "Please confirm by saying 'yes proceed' or 'cancel'"
    })


# ==================== SESSION & MEMORY ====================

async def _take_snapshot(engine, name: str = "snapshot", **_) -> str:
    """Take snapshot of all tabs (DOM text + URLs)."""
    snapshot = {}
    for tab_id, page in engine.pages.items():
        engine.active_tab_id = tab_id
        snapshot[tab_id] = {
            "url": page.url,
            "title": await page.title(),
            "text_preview": (await _get_text(engine))[:500]
        }
    
    engine.sessions[f"snapshot_{name}"] = snapshot
    return json.dumps(snapshot, indent=2)


async def _get_action_history(engine, last_n: int = 20, **_) -> str:
    """Return last N actions performed."""
    history = engine.action_log[-last_n:]
    return json.dumps(history, indent=2)


async def _activity_summary(engine, **_) -> str:
    """Human-readable summary of what the browser did."""
    history = engine.action_log[-30:]
    if not history:
        return "No actions performed yet."
    
    model = _get_gemini()
    resp = model.generate_content(
        f"Convert this action log into a human-readable summary of what was done. Be concise:\n\n{json.dumps(history)}",
        generation_config=genai.GenerationConfig(max_output_tokens=300, temperature=0.3)
    )
    return resp.text
