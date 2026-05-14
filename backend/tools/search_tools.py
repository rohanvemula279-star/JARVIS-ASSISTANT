"""
Search Tools — Web search capabilities.
Uses DuckDuckGo (free, no key) with optional SerpAPI/Tavily upgrade.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from backend.config.settings import get_settings
from backend.tools.registry import registry, ToolDefinition, ToolParameter

logger = logging.getLogger("tools.search")


async def web_search_handler(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Search the web using DuckDuckGo Instant Answer API (free, no key needed)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # DuckDuckGo Instant Answer API
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_redirect": 1,
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            data = response.json()

        results = []

        # Abstract (main answer)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", ""),
                "snippet": data["Abstract"],
                "url": data.get("AbstractURL", ""),
                "source": data.get("AbstractSource", ""),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })

        # Answer (if available)
        if data.get("Answer"):
            results.insert(0, {
                "title": "Direct Answer",
                "snippet": data["Answer"],
                "url": "",
            })

        if not results:
            return {
                "query": query,
                "results": [],
                "message": f"No instant answers found for '{query}'. Try a more specific query.",
            }

        return {"query": query, "result_count": len(results), "results": results}

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {"query": query, "results": [], "error": str(e)}


# Register search tools
registry.register(ToolDefinition(
    name="web_search",
    description="Search the web for information using DuckDuckGo. Returns summaries and links.",
    parameters=[
        ToolParameter("query", "string", "The search query"),
        ToolParameter("num_results", "number", "Max number of results (default 5)", required=False),
    ],
    handler=web_search_handler,
    category="search",
))
