import json
import unittest
from unittest.mock import patch

from tools.web_search import WebSearchTool


class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class WebSearchToolTests(unittest.TestCase):
    def test_returns_results_from_duckduckgo_payload(self):
        payload = {
            "Heading": "Energia solar",
            "AbstractText": "Energia solar converte luz em eletricidade.",
            "AbstractURL": "https://example.org/solar",
            "RelatedTopics": [
                {"Text": "Painel solar - modulo fotovoltaico", "FirstURL": "https://example.org/painel"}
            ],
        }
        tool = WebSearchTool(timeout=3)
        with patch("tools.web_search.request.urlopen", return_value=_FakeHTTPResponse(json.dumps(payload).encode("utf-8"))):
            result = tool.run(query="energia solar", limit=3)

        self.assertEqual(result["event"], "web_search")
        self.assertGreaterEqual(result["count"], 1)
        self.assertIn("energia solar", result["query"])
        self.assertIn("Pesquisa web", result["message"])

    def test_handles_network_errors(self):
        tool = WebSearchTool(timeout=3)
        with patch("tools.web_search.request.urlopen", side_effect=RuntimeError("sem internet")):
            result = tool.run(query="cotacao dolar", limit=3)

        self.assertIn("error", result)
        self.assertIn("sem internet", result["error"])
        self.assertIn("Nao consegui pesquisar", result["message"])

    def test_rejects_empty_query(self):
        tool = WebSearchTool(timeout=3)
        result = tool.run(query="  ")
        self.assertIn("error", result)
        self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
