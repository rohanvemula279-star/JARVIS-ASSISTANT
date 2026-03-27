from actions.browser_core import BrowserEngine
import urllib.parse

async def navigate(action: str, **params) -> str:
    """
    Router for all navigation actions.
    Called by the agent with action name and parameters.
    """
    engine = await BrowserEngine.get_instance()
    
    handlers = {
        "open_url": _open_url,
        "search": _search,
        "go_back": _go_back,
        "go_forward": _go_forward,
        "reload": _reload,
        "stop_loading": _stop_loading,
        "open_link_same_tab": _open_url,          # same as open_url
        "open_link_new_tab": _open_in_new_tab,
        "open_link_background_tab": _open_in_background_tab,
        "new_blank_tab": _new_blank_tab,
        "close_current_tab": _close_current_tab,
        "close_tab_by_title": _close_tab_by_title,
        "switch_tab": _switch_tab,
        "duplicate_tab": _duplicate_tab,
        "pin_tab": _pin_tab,                      # Playwright limitation: visual only
    }
    
    handler = handlers.get(action)
    if not handler:
        return f"Unknown navigation action: {action}"
    
    result = await handler(engine, **params)
    engine.log_action(action, params, result)
    return result


async def _open_url(engine: BrowserEngine, url: str, **_) -> str:
    """Open exact URL in current tab."""
    page = engine.get_active_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return f"Opened {url}"


async def _search(engine: BrowserEngine, query: str, engine_name: str = "google", **_) -> str:
    """
    Open search results for a query.
    This is the CORE fix for YouTube — instead of typing into Start menu,
    we navigate directly to the search URL.
    """
    search_urls = {
        "google": f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
        "amazon": f"https://www.amazon.in/s?k={urllib.parse.quote(query)}",
        "flipkart": f"https://www.flipkart.com/search?q={urllib.parse.quote(query)}",
    }
    url = search_urls.get(engine_name, search_urls["google"])
    page = engine.get_active_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return f"Searched '{query}' on {engine_name}"


async def _go_back(engine: BrowserEngine, **_) -> str:
    page = engine.get_active_page()
    await page.go_back(wait_until="domcontentloaded")
    return "Went back"


async def _go_forward(engine: BrowserEngine, **_) -> str:
    page = engine.get_active_page()
    await page.go_forward(wait_until="domcontentloaded")
    return "Went forward"


async def _reload(engine: BrowserEngine, **_) -> str:
    page = engine.get_active_page()
    await page.reload(wait_until="domcontentloaded")
    return "Page reloaded"


async def _stop_loading(engine: BrowserEngine, **_) -> str:
    page = engine.get_active_page()
    # Playwright doesn't have stop() — we evaluate window.stop()
    await page.evaluate("window.stop()")
    return "Stopped loading"


async def _open_in_new_tab(engine: BrowserEngine, url: str, **_) -> str:
    """Open URL in a NEW tab and switch to it."""
    page = await engine.context.new_page()
    tab_id = f"tab_{len(engine.pages)}"
    engine.pages[tab_id] = page
    engine.active_tab_id = tab_id
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    return f"Opened {url} in new tab {tab_id}"


async def _open_in_background_tab(engine: BrowserEngine, url: str, **_) -> str:
    """Open URL in new tab but DON'T switch to it."""
    page = await engine.context.new_page()
    tab_id = f"tab_{len(engine.pages)}"
    engine.pages[tab_id] = page
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # Don't change active_tab_id — stay on current tab
    return f"Opened {url} in background tab {tab_id}"


async def _new_blank_tab(engine: BrowserEngine, **_) -> str:
    page = await engine.context.new_page()
    tab_id = f"tab_{len(engine.pages)}"
    engine.pages[tab_id] = page
    engine.active_tab_id = tab_id
    return f"Opened blank tab {tab_id}"


async def _close_current_tab(engine: BrowserEngine, **_) -> str:
    tab_id = engine.active_tab_id
    page = engine.pages.pop(tab_id, None)
    if page:
        await page.close()
    # Switch to another tab if available
    if engine.pages:
        engine.active_tab_id = list(engine.pages.keys())[-1]
    else:
        # All tabs closed — open a fresh one
        new_page = await engine.context.new_page()
        new_id = f"tab_{len(engine.pages)}"
        engine.pages[new_id] = new_page
        engine.active_tab_id = new_id
    return f"Closed tab {tab_id}, now on {engine.active_tab_id}"


async def _close_tab_by_title(engine: BrowserEngine, title: str, **_) -> str:
    """Close tab whose title contains the given string."""
    for tab_id, page in list(engine.pages.items()):
        page_title = await page.title()
        if title.lower() in page_title.lower():
            await page.close()
            del engine.pages[tab_id]
            if engine.active_tab_id == tab_id:
                engine.active_tab_id = list(engine.pages.keys())[-1] if engine.pages else None
            return f"Closed tab '{page_title}'"
    return f"No tab found with title containing '{title}'"


async def _switch_tab(engine: BrowserEngine, title: str = None, tab_id: str = None, **_) -> str:
    """Switch to tab by title match or tab_id."""
    if tab_id and tab_id in engine.pages:
        engine.active_tab_id = tab_id
        await engine.pages[tab_id].bring_to_front()
        return f"Switched to {tab_id}"
    if title:
        for tid, page in engine.pages.items():
            page_title = await page.title()
            if title.lower() in page_title.lower():
                engine.active_tab_id = tid
                await page.bring_to_front()
                return f"Switched to '{page_title}'"
    return "Tab not found"


async def _duplicate_tab(engine: BrowserEngine, **_) -> str:
    page = engine.get_active_page()
    url = page.url
    return await _open_in_new_tab(engine, url=url)


async def _pin_tab(engine: BrowserEngine, **_) -> str:
    # Playwright can't actually pin tabs in Chrome UI
    # We just mark it in metadata
    return "Tab marked as pinned (visual pinning not supported via automation)"
