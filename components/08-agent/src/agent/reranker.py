"""
Reranker — calls an external reranker model to re-score vector search results.

Flow: vector search (top-K candidates) → reranker (cross-encoder) → top-N to LLM

Controlled by environment variables:
    RERANK_ENABLED   — "true" to enable, anything else to disable (default: "false")
    RERANKER_URL     — endpoint e.g. https://.../v1/rerank
    RERANKER_MODEL   — model name e.g. qwen3-reranker-06b
    RERANK_TOP_K     — candidates to fetch from vector search (default: 20)
    RERANK_TOP_N     — top results after reranking (default: 5)
"""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

RERANK_ENABLED = os.getenv("RERANK_ENABLED", "false").lower() == "true"
RERANKER_URL = os.getenv("RERANKER_URL", "")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "20"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))


def is_enabled() -> bool:
    return RERANK_ENABLED and bool(RERANKER_URL) and bool(RERANKER_MODEL)


def rerank(query: str, documents: list) -> list:
    """Rerank documents and return top-N with relevance scores.
    Returns list of dicts: [{"text": str, "score": float}, ...]
    Falls back to original order if the reranker call fails.
    """
    if not documents:
        return []

    try:
        resp = httpx.post(
            RERANKER_URL,
            json={
                "model": RERANKER_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(RERANK_TOP_N, len(documents)),
            },
            verify=False,
            timeout=30,
        )
        resp.raise_for_status()

        results = resp.json().get("results", [])
        reranked = [
            {"text": documents[r["index"]], "score": r.get("relevance_score", 0.0)}
            for r in results
        ]
        logger.info("[RERANK] %d → %d docs (top=%.3f)",
                    len(documents), len(reranked),
                    reranked[0]["score"] if reranked else 0.0)
        return reranked

    except Exception as e:
        logger.warning("[RERANK] Failed, using original order: %s", e)
        return [{"text": doc, "score": 0.0} for doc in documents[:RERANK_TOP_N]]
