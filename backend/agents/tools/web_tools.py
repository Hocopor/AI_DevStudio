"""
Web research tools.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx
from loguru import logger

from agents.tools.registry import ToolParam, ToolResult, tool


@tool(
    name="web_search",
    description="Search the web and return titles, links, and snippets.",
    params=[
        ToolParam("query", "string", "Search query.", required=True),
        ToolParam("num_results", "integer", "Number of results (1-10).", required=False),
    ],
)
async def web_search(query: str, ctx, num_results: int = 5) -> ToolResult:
    num_results = max(1, min(10, num_results))
    try:
        results = await _ddg_search(query, num_results)
        if not results:
            return ToolResult(ok=True, output=f"No results found for '{query}'.", data=[])

        lines = [f"Results for '{query}':"]
        for index, result in enumerate(results, start=1):
            lines.append(f"{index}. {result['title']}")
            lines.append(f"   URL: {result['url']}")
            if result.get("snippet"):
                lines.append(f"   {result['snippet'][:200]}")
        return ToolResult(ok=True, output="\n".join(lines), data=results)
    except Exception as exc:
        logger.error(f"web_search error: {exc}")
        return ToolResult(ok=False, output="", error=str(exc))


async def _ddg_search(query: str, num: int) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AI DevStudio Research Bot)"},
        follow_redirects=True,
    ) as client:
        resp = await client.get("https://html.duckduckgo.com/html/", params={"q": query})
        if resp.status_code != 200:
            raise RuntimeError(f"DuckDuckGo returned {resp.status_code}")

    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results = []
            self._in_result = False
            self._current = {}
            self._capture = None

        def handle_starttag(self, tag, attrs):
            attrs_map = dict(attrs)
            css_class = attrs_map.get("class", "")
            if "result__title" in css_class:
                self._current = {}
                self._in_result = True
            if self._in_result and tag == "a" and "result__a" in css_class:
                href = attrs_map.get("href", "")
                if href.startswith("http"):
                    self._current["url"] = href
                self._capture = "title"
            if self._in_result and "result__snippet" in css_class:
                self._capture = "snippet"

        def handle_data(self, data):
            if self._capture and data.strip():
                self._current[self._capture] = self._current.get(self._capture, "") + data.strip()

        def handle_endtag(self, tag):
            if tag == "a" and self._capture == "title":
                self._capture = None
            if tag == "div" and self._in_result and self._current.get("url"):
                if "title" in self._current:
                    self.results.append(self._current.copy())
                self._current = {}
                self._in_result = False
                self._capture = None

    parser = DDGParser()
    parser.feed(resp.text)
    return parser.results[:num]


@tool(
    name="web_fetch",
    description="Fetch the text content of a web page by URL.",
    params=[
        ToolParam("url", "string", "Page URL.", required=True),
        ToolParam("max_chars", "integer", "Maximum returned characters.", required=False),
    ],
)
async def web_fetch(url: str, ctx, max_chars: int = 3000) -> ToolResult:
    if not url.startswith(("http://", "https://")):
        return ToolResult(ok=False, output="", error="URL must start with http:// or https://")

    try:
        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            return ToolResult(ok=False, output="", error=f"HTTP {resp.status_code}")

        text = _extract_text(resp.text)[:max_chars]
        return ToolResult(ok=True, output=f"Content of {url}:\n\n{text}")
    except httpx.TimeoutException:
        return ToolResult(ok=False, output="", error="Timed out while loading the page.")
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


def _extract_text(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return (
        html.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&quot;", '"')
        .strip()
    )
