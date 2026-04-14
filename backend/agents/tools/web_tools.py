"""
Web research tools.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlparse

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
        results = await _search_web(query, num_results)
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


def _normalize_result_url(url: str) -> str:
    if not url:
        return ""
    if "duckduckgo.com/l/?" in url:
        parsed = urlparse(url)
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return url


def _dedupe_results(results: list[dict], limit: int) -> list[dict]:
    deduped = []
    seen = set()
    for item in results:
        url = _normalize_result_url(item.get("url", "")).strip()
        title = (item.get("title") or "").strip()
        if not url or not title or url in seen:
            continue
        seen.add(url)
        deduped.append({"title": title, "url": url, "snippet": (item.get("snippet") or "").strip()})
        if len(deduped) >= limit:
            break
    return deduped


class DDGHTMLParser(HTMLParser):
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
            self._current["url"] = attrs_map.get("href", "")
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


class DDGLiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = {}
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attrs_map = dict(attrs)
        href = attrs_map.get("href", "")
        if tag == "a" and href.startswith(("http", "/l/?")):
            self._current = {"url": href}
            self._capture = "title"

    def handle_data(self, data):
        if self._capture and data.strip():
            self._current[self._capture] = self._current.get(self._capture, "") + data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self._capture == "title":
            if self._current.get("url") and self._current.get("title"):
                self.results.append(self._current.copy())
            self._capture = None
            self._current = {}


class BingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = {}
        self._capture = None
        self._in_result = False

    def handle_starttag(self, tag, attrs):
        attrs_map = dict(attrs)
        css_class = attrs_map.get("class", "")
        if tag == "li" and "b_algo" in css_class:
            self._in_result = True
            self._current = {}
        elif self._in_result and tag == "a" and not self._current.get("url"):
            self._current["url"] = attrs_map.get("href", "")
            self._capture = "title"
        elif self._in_result and tag == "p":
            self._capture = "snippet"

    def handle_data(self, data):
        if self._capture and data.strip():
            self._current[self._capture] = self._current.get(self._capture, "") + data.strip()

    def handle_endtag(self, tag):
        if tag == "li" and self._in_result:
            if self._current.get("url") and self._current.get("title"):
                self.results.append(self._current.copy())
            self._in_result = False
            self._current = {}
            self._capture = None
        elif tag in {"a", "p"}:
            self._capture = None


async def _search_web(query: str, num: int) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; AI DevStudio Research Bot)"},
        follow_redirects=True,
    ) as client:
        providers = [
            ("ddg_html", "https://html.duckduckgo.com/html/", {"q": query}, DDGHTMLParser),
            ("ddg_lite", "https://lite.duckduckgo.com/lite/", {"q": query}, DDGLiteParser),
            ("bing", f"https://www.bing.com/search?q={quote(query)}&count={num}", None, BingParser),
        ]
        errors = []
        for name, url, params, parser_cls in providers:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    errors.append(f"{name}: HTTP {resp.status_code}")
                    continue
                parser = parser_cls()
                parser.feed(resp.text)
                results = _dedupe_results(parser.results, num)
                if results:
                    return results
                errors.append(f"{name}: no parseable results")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue

    raise RuntimeError("Search providers failed: " + " | ".join(errors))


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
