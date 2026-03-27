from actions.browser_core import BrowserEngine
import google.generativeai as genai
from memory.config_manager import get_gemini_key
import json
import os


# Configure Gemini once — uses your existing API key
_gemini_model = None

def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        genai.configure(api_key=get_gemini_key())
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


async def extract(action: str, **params) -> str:
    """Router for all extraction actions."""
    engine = await BrowserEngine.get_instance()
    
    handlers = {
        "get_text": _get_text,
        "get_html": _get_html,
        "get_element_text": _get_element_text,
        "get_attribute": _get_attribute,
        "is_visible": _is_visible,
        "is_enabled": _is_enabled,
        "get_title": _get_title,
        "get_url": _get_url,
        "extract_links": _extract_links,
        "extract_images": _extract_images,
        "extract_tables": _extract_tables,
        "extract_forms": _extract_forms,
        "summarize_page": _summarize_page,
        "summarize_section": _summarize_section,
        "classify_page": _classify_page,
    }
    
    handler = handlers.get(action)
    if not handler:
        return f"Unknown extraction action: {action}"
    
    result = await handler(engine, **params)
    engine.log_action(action, params, str(result)[:200])
    return result


async def _get_text(engine, **_) -> str:
    """Get main page text, boilerplate removed."""
    page = engine.get_active_page()
    # Extract text, strip nav/footer/sidebar noise
    text = await page.evaluate("""
    () => {
        // Remove nav, footer, sidebar, ads
        const remove = ['nav', 'footer', 'aside', 'header', '[role="navigation"]',
                        '[role="banner"]', '[role="contentinfo"]', '.ad', '.advertisement'];
        const clone = document.body.cloneNode(true);
        remove.forEach(sel => {
            clone.querySelectorAll(sel).forEach(el => el.remove());
        });
        return clone.innerText.replace(/\\n{3,}/g, '\\n\\n').trim();
    }
    """)
    # Truncate to save tokens
    return text[:15000] if len(text) > 15000 else text


async def _get_html(engine, **_) -> str:
    page = engine.get_active_page()
    html = await page.content()
    return html[:30000]


async def _get_element_text(engine, selector: str, **_) -> str:
    page = engine.get_active_page()
    el = page.locator(selector).first
    if await el.count() > 0:
        return await el.inner_text()
    return "Element not found"


async def _get_attribute(engine, selector: str, attribute: str, **_) -> str:
    page = engine.get_active_page()
    val = await page.get_attribute(selector, attribute)
    return val or "Attribute not found"


async def _is_visible(engine, selector: str, **_) -> str:
    page = engine.get_active_page()
    el = page.locator(selector).first
    if await el.count() > 0:
        visible = await el.is_visible()
        return f"{'Visible' if visible else 'Not visible'}"
    return "Element not found"


async def _is_enabled(engine, selector: str, **_) -> str:
    page = engine.get_active_page()
    el = page.locator(selector).first
    if await el.count() > 0:
        enabled = await el.is_enabled()
        return f"{'Enabled' if enabled else 'Disabled'}"
    return "Element not found"


async def _get_title(engine, **_) -> str:
    page = engine.get_active_page()
    return await page.title()


async def _get_url(engine, **_) -> str:
    page = engine.get_active_page()
    return page.url


async def _extract_links(engine, **_) -> str:
    page = engine.get_active_page()
    links = await page.evaluate("""
    () => Array.from(document.querySelectorAll('a[href]')).slice(0, 50).map(a => ({
        text: a.innerText.trim().substring(0, 100),
        url: a.href
    })).filter(l => l.text.length > 0)
    """)
    return json.dumps(links, indent=2)


async def _extract_images(engine, **_) -> str:
    page = engine.get_active_page()
    images = await page.evaluate("""
    () => Array.from(document.querySelectorAll('img[src]')).slice(0, 30).map(img => ({
        alt: img.alt || '',
        src: img.src
    }))
    """)
    return json.dumps(images, indent=2)


async def _extract_tables(engine, **_) -> str:
    page = engine.get_active_page()
    tables = await page.evaluate("""
    () => Array.from(document.querySelectorAll('table')).slice(0, 5).map(table => {
        const rows = Array.from(table.querySelectorAll('tr'));
        return rows.map(row => 
            Array.from(row.querySelectorAll('td, th')).map(cell => cell.innerText.trim())
        );
    })
    """)
    return json.dumps(tables, indent=2)


async def _extract_forms(engine, **_) -> str:
    page = engine.get_active_page()
    forms = await page.evaluate("""
    () => Array.from(document.querySelectorAll('form')).slice(0, 5).map((form, i) => ({
        id: form.id || `form_${i}`,
        action: form.action,
        method: form.method,
        fields: Array.from(form.querySelectorAll('input, select, textarea')).map(f => ({
            type: f.type || f.tagName.toLowerCase(),
            name: f.name,
            id: f.id,
            placeholder: f.placeholder || '',
            required: f.required
        }))
    }))
    """)
    return json.dumps(forms, indent=2)


async def _summarize_page(engine, **_) -> str:
    """Summarize current page using Gemini. Token-efficient."""
    text = await _get_text(engine)
    if len(text) < 50:
        return "Page has too little content to summarize."
    
    # Truncate to save tokens — 5000 chars is enough for a good summary
    text_for_summary = text[:5000]
    
    model = _get_gemini()
    response = model.generate_content(
        f"Summarize this webpage content concisely in 3-5 bullet points:\n\n{text_for_summary}",
        generation_config=genai.GenerationConfig(
            max_output_tokens=300,
            temperature=0.3
        )
    )
    return response.text


async def _summarize_section(engine, selector: str = None, text: str = None, **_) -> str:
    """Summarize specific section of the page."""
    if selector:
        section_text = await _get_element_text(engine, selector=selector)
    elif text:
        section_text = text
    else:
        return "Provide selector or text to summarize"
    
    model = _get_gemini()
    response = model.generate_content(
        f"Summarize this concisely:\n\n{section_text[:3000]}",
        generation_config=genai.GenerationConfig(
            max_output_tokens=200,
            temperature=0.3
        )
    )
    return response.text


async def _classify_page(engine, **_) -> str:
    """Classify what type of page this is."""
    page = engine.get_active_page()
    title = await page.title()
    url = page.url
    text_snippet = (await _get_text(engine))[:1000]
    
    model = _get_gemini()
    response = model.generate_content(
        f"""Classify this webpage into ONE category:
[news, product, shopping, docs, blog, email, social_media, video, search_results, login, form, other]

Title: {title}
URL: {url}
Content preview: {text_snippet[:500]}

Reply with just the category name.""",
        generation_config=genai.GenerationConfig(
            max_output_tokens=20,
            temperature=0.1
        )
    )
    return response.text.strip()
