import json
from urllib import parse, request

from tools.base import Tool


class WebSearchTool(Tool):
    name = "web_search"
    description = "Pesquisa informacoes na internet usando DuckDuckGo Instant Answer API."

    def __init__(self, timeout: int = 8):
        self.timeout = max(2, int(timeout))

    def run(self, query="", limit=3, **kwargs):
        query = str(query or "").strip()
        if not query:
            return {
                "event": "web_search",
                "query": query,
                "count": 0,
                "results": [],
                "error": "Consulta vazia para pesquisa web.",
                "message": "Informe um tema para pesquisar na internet.",
            }

        limit = max(1, int(limit))
        try:
            payload = self._fetch(query)
            results = self._extract_results(payload, limit=limit)
        except Exception as exc:
            return {
                "event": "web_search",
                "query": query,
                "count": 0,
                "results": [],
                "error": str(exc),
                "message": f"Nao consegui pesquisar na internet agora: {exc}",
            }

        if not results:
            return {
                "event": "web_search",
                "query": query,
                "count": 0,
                "results": [],
                "message": f"Nao encontrei resultados relevantes para '{query}'.",
            }

        summary = " | ".join(f"{idx}. {item['title']}" for idx, item in enumerate(results, start=1))
        return {
            "event": "web_search",
            "query": query,
            "count": len(results),
            "results": results,
            "message": f"Pesquisa web para '{query}': {summary}",
        }

    def _fetch(self, query):
        params = parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_html": "1",
                "no_redirect": "1",
                "skip_disambig": "1",
            }
        )
        url = f"https://api.duckduckgo.com/?{params}"
        req = request.Request(url, headers={"User-Agent": "JarvisWebSearch/1.0"})
        with request.urlopen(req, timeout=self.timeout) as response:  # nosec B310
            raw = response.read().decode("utf-8", errors="ignore")
        return json.loads(raw or "{}")

    def _extract_results(self, payload, limit=3):
        results = []

        abstract = str(payload.get("AbstractText", "")).strip()
        if abstract:
            results.append(
                {
                    "title": str(payload.get("Heading", "Resumo direto")).strip() or "Resumo direto",
                    "snippet": abstract,
                    "url": str(payload.get("AbstractURL", "")).strip(),
                }
            )

        for item in payload.get("Results", []) or []:
            if len(results) >= limit:
                break
            text = str(item.get("Text", "")).strip()
            if not text:
                continue
            results.append(
                {
                    "title": text.split(" - ", 1)[0][:120],
                    "snippet": text,
                    "url": str(item.get("FirstURL", "")).strip(),
                }
            )

        for topic in self._flatten_related(payload.get("RelatedTopics", []) or []):
            if len(results) >= limit:
                break
            text = str(topic.get("Text", "")).strip()
            if not text:
                continue
            results.append(
                {
                    "title": text.split(" - ", 1)[0][:120],
                    "snippet": text,
                    "url": str(topic.get("FirstURL", "")).strip(),
                }
            )

        unique = []
        seen = set()
        for item in results:
            key = (item.get("title", ""), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= limit:
                break
        return unique

    def _flatten_related(self, related_topics):
        flattened = []
        for topic in related_topics:
            nested = topic.get("Topics")
            if isinstance(nested, list):
                flattened.extend(self._flatten_related(nested))
                continue
            flattened.append(topic)
        return flattened
