"""
Reranker client for post-retrieval reranking of knowledge_search results.

Calls an external reranker model endpoint (e.g. Qwen3-Reranker) to reorder
vector search results by semantic relevance before the LLM reasons over them.

Flow: knowledge_search (vector similarity) → reranker (cross-encoder) → top-N to LLM
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

RERANKER_URL = os.getenv("RERANKER_URL", "")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "")
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))


class Reranker:
    """Rerank documents via an external vLLM /v1/rerank endpoint."""

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        top_n: Optional[int] = None,
    ):
        self.url = url or RERANKER_URL
        self.model = model or RERANKER_MODEL
        self.top_n = top_n or RERANK_TOP_N
        self.enabled = bool(self.url and self.model)

        if self.enabled:
            logger.info(
                "Reranker enabled: url=%s model=%s top_n=%d",
                self.url, self.model, self.top_n,
            )
        else:
            logger.info("Reranker disabled (RERANKER_URL or RERANKER_MODEL not set)")

    def rerank(self, query: str, documents: List[str]) -> List[Dict[str, Any]]:
        """Rerank documents and return the top-N with relevance scores.

        Args:
            query: The user's search query.
            documents: List of document text strings from vector search.

        Returns:
            List of dicts with keys: index, text, relevance_score.
            Sorted by relevance_score descending.
            Falls back to original order if reranker is unavailable.
        """
        if not self.enabled or not documents:
            return [
                {"index": i, "text": doc, "relevance_score": 0.0}
                for i, doc in enumerate(documents)
            ]

        try:
            resp = httpx.post(
                self.url,
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": min(self.top_n, len(documents)),
                },
                verify=False,
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

            reranked = []
            for r in results:
                idx = r["index"]
                reranked.append({
                    "index": idx,
                    "text": documents[idx],
                    "relevance_score": r.get("relevance_score", 0.0),
                })

            logger.info(
                "Reranked %d → %d documents (top score=%.3f)",
                len(documents), len(reranked),
                reranked[0]["relevance_score"] if reranked else 0.0,
            )
            return reranked

        except Exception as e:
            logger.warning("Reranker call failed, using original order: %s", e)
            return [
                {"index": i, "text": doc, "relevance_score": 0.0}
                for i, doc in enumerate(documents)
            ]
