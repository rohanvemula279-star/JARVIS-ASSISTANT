from actions.browser_core import BrowserEngine
import asyncio


async def interact(action: str, **params) -> str:
    """Router for all page interaction actions."""
    engine = await BrowserEngine.get_instance()
    
    handlers = {
        "click": _click,
        "double_click": _double_click,
        "right_click": _right_click,
        "scroll_to_top": _scroll_to_top,
        "scroll_to_bottom": _scroll_to_bottom,
        "scroll_by": _scroll_by,
        "scroll_container": _scroll_container,
        "hover": _hover,
        "focus": _focus,
        "type_text": _type_text,
        "fill_text": _fill_text,
        "clear_input": _clear_input,
        "select_dropdown": _select_dropdown,
        "check_checkbox": _check_checkbox,
        "uncheck_checkbox": _uncheck_checkbox,
        "click_radio": _click_radio,
        "press_key": _press_key,
        "drag_and_drop": _drag_and_drop,
        "upload_file": _upload_file,
        "submit_form": _submit_form,
        "close_popup": _close_popup,
    }
    
    handler = handlers.get(action)
    if not handler:
        return f"Unknown interaction action: {action}"
    
    result = await handler(engine, **params)
    engine.log_action(action, params, result)
    return result


async def _find_element(page, selector: str = None, text: str = None):
    """
    Smart element finder. Tries:
    1. CSS selector if provided
    2. Text-based search (finds clickable element containing the text)
    3. Role-based fallback
    """
    if selector:
        try:
            el = page.locator(selector).first
            if await el.count() > 0:
                return el
        except:
            pass
    
    if text:
        # Try exact text match on interactive elements
        for role in ["link", "button", "menuitem"]:
            el = page.get_by_role(role, name=text, exact=False)
            if await el.count() > 0:
                return el.first
        
        # Fallback: any element containing this text
        el = page.get_by_text(text, exact=False).first
        if await el.count() > 0:
            return el
    
    return None


async def _click(engine, selector: str = None, text: str = None, **_) -> str:
    """Click element by CSS selector or visible text."""
    page = engine.get_active_page()
    el = await _find_element(page, selector, text)
    if el:
        await el.click(timeout=10000)
        target = selector or text
        return f"Clicked '{target}'"
    return f"Element not found: selector={selector}, text={text}"


async def _double_click(engine, selector: str = None, text: str = None, **_) -> str:
    page = engine.get_active_page()
    el = await _find_element(page, selector, text)
    if el:
        await el.dblclick(timeout=10000)
        return f"Double-clicked '{selector or text}'"
    return "Element not found"


async def _right_click(engine, selector: str = None, text: str = None, **_) -> str:
    page = engine.get_active_page()
    el = await _find_element(page, selector, text)
    if el:
        await el.click(button="right", timeout=10000)
        return f"Right-clicked '{selector or text}'"
    return "Element not found"


async def _scroll_to_top(engine, **_) -> str:
    page = engine.get_active_page()
    await page.evaluate("window.scrollTo(0, 0)")
    return "Scrolled to top"


async def _scroll_to_bottom(engine, **_) -> str:
    page = engine.get_active_page()
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    return "Scrolled to bottom"


async def _scroll_by(engine, pixels: int = 500, direction: str = "down", **_) -> str:
    page = engine.get_active_page()
    y = pixels if direction == "down" else -pixels
    await page.evaluate(f"window.scrollBy(0, {y})")
    return f"Scrolled {direction} by {pixels}px"


async def _scroll_container(engine, selector: str, pixels: int = 300, **_) -> str:
    page = engine.get_active_page()
    await page.evaluate(f"document.querySelector('{selector}').scrollBy(0, {pixels})")
    return f"Scrolled container '{selector}' by {pixels}px"


async def _hover(engine, selector: str = None, text: str = None, **_) -> str:
    page = engine.get_active_page()
    el = await _find_element(page, selector, text)
    if el:
        await el.hover(timeout=10000)
        return f"Hovering over '{selector or text}'"
    return "Element not found"


async def _focus(engine, selector: str, **_) -> str:
    page = engine.get_active_page()
    await page.focus(selector)
    return f"Focused '{selector}'"


async def _type_text(engine, selector: str = None, text: str = "", delay: int = 50, **_) -> str:
    """Type text character by character (simulates human typing)."""
    page = engine.get_active_page()
    if selector:
        await page.click(selector)
    await page.keyboard.type(text, delay=delay)
    return f"Typed '{text[:50]}...'"


async def _fill_text(engine, selector: str, text: str, **_) -> str:
    """Instantly fill input field (faster than type_text)."""
    page = engine.get_active_page()
    await page.fill(selector, text)
    return f"Filled '{selector}' with '{text[:50]}'"


async def _clear_input(engine, selector: str, **_) -> str:
    page = engine.get_active_page()
    await page.fill(selector, "")
    return f"Cleared '{selector}'"


async def _select_dropdown(engine, selector: str, value: str = None, label: str = None, **_) -> str:
    page = engine.get_active_page()
    if value:
        await page.select_option(selector, value=value)
    elif label:
        await page.select_option(selector, label=label)
    return f"Selected '{value or label}' in '{selector}'"


async def _check_checkbox(engine, selector: str = None, text: str = None, **_) -> str:
    page = engine.get_active_page()
    if selector:
        await page.check(selector)
    elif text:
        await page.get_by_label(text).check()
    return f"Checked '{selector or text}'"


async def _uncheck_checkbox(engine, selector: str = None, text: str = None, **_) -> str:
    page = engine.get_active_page()
    if selector:
        await page.uncheck(selector)
    elif text:
        await page.get_by_label(text).uncheck()
    return f"Unchecked '{selector or text}'"


async def _click_radio(engine, selector: str = None, text: str = None, **_) -> str:
    return await _click(engine, selector=selector, text=text)


async def _press_key(engine, key: str, **_) -> str:
    """Press keyboard key: Enter, Tab, Escape, ArrowDown, etc."""
    page = engine.get_active_page()
    await page.keyboard.press(key)
    return f"Pressed '{key}'"


async def _drag_and_drop(engine, source_selector: str, target_selector: str, **_) -> str:
    page = engine.get_active_page()
    await page.drag_and_drop(source_selector, target_selector)
    return f"Dragged '{source_selector}' to '{target_selector}'"


async def _upload_file(engine, selector: str, file_path: str, **_) -> str:
    page = engine.get_active_page()
    await page.set_input_files(selector, file_path)
    return f"Uploaded '{file_path}'"


async def _submit_form(engine, selector: str = "form", **_) -> str:
    page = engine.get_active_page()
    await page.evaluate(f"document.querySelector('{selector}').submit()")
    return "Form submitted"


async def _close_popup(engine, selector: str = None, **_) -> str:
    """Close popup/modal/cookie banner. Tries common patterns if no selector given."""
    page = engine.get_active_page()
    
    if selector:
        try:
            await page.click(selector, timeout=3000)
            return f"Closed popup using '{selector}'"
        except:
            pass
    
    # Common popup close patterns
    close_selectors = [
        "[aria-label='Close']",
        "[aria-label='Dismiss']",
        "button:has-text('Accept')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "button:has-text('No thanks')",
        "button:has-text('Accept all')",
        ".modal-close",
        ".popup-close",
        "#close-button",
    ]
    
    for sel in close_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=2000)
                return f"Closed popup using '{sel}'"
        except:
            continue
    
    return "No popup found to close"
