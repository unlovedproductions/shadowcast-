"""Local RAG stores: job-scoped product research and style-rules corpus retrieval."""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SENTENCE_CHUNK_MAX = 1200
SENTENCE_OVERLAP = 1
HYBRID_DENSE_WEIGHT = 0.45
HYBRID_LEXICAL_WEIGHT = 0.35
HYBRID_BM25_WEIGHT = 0.20

RerankFn = Callable[[str, list[dict[str, Any]]], list[dict[str, Any]]]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_text_sentences(
    text: str,
    *,
    max_size: int = SENTENCE_CHUNK_MAX,
    overlap_sentences: int = SENTENCE_OVERLAP,
) -> list[str]:
    """Sentence-based chunking per chunking.json recommendation."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    sentences = _split_sentences(text)
    if not sentences:
        return [text] if text else []
    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(sentences):
        parts: list[str] = []
        size = 0
        idx = start
        while idx < len(sentences):
            candidate = sentences[idx]
            extra = len(candidate) + (1 if parts else 0)
            if parts and size + extra > max_size:
                break
            parts.append(candidate)
            size += extra
            idx += 1
        if parts:
            chunks.append(" ".join(parts))
        if idx >= len(sentences):
            break
        next_start = max(start + 1, idx - overlap_sentences)
        if next_start <= start:
            break
        start = next_start
    return [c for c in chunks if c]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Fixed-size char chunking (legacy fallback)."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _lexical_score(query: str, chunk: str) -> float:
    q = _token_set(query)
    c = _token_set(chunk)
    if not q or not c:
        return 0.0
    return len(q & c) / len(q)


class _BM25Index:
    """Lightweight BM25 index for hybrid lexical retrieval."""

    def __init__(self, docs: dict[str, str], *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids = list(docs.keys())
        self.doc_tokens: dict[str, list[str]] = {}
        self.doc_lengths: dict[str, int] = {}
        self.df: Counter[str] = Counter()
        for doc_id, text in docs.items():
            tokens = _tokenize(text)
            self.doc_tokens[doc_id] = tokens
            self.doc_lengths[doc_id] = len(tokens)
            for term in set(tokens):
                self.df[term] += 1
        self.avg_dl = sum(self.doc_lengths.values()) / len(self.doc_lengths) if self.doc_lengths else 0.0
        self.num_docs = len(self.doc_ids)

    def score(self, query: str, doc_id: str) -> float:
        tokens = self.doc_tokens.get(doc_id, [])
        if not tokens:
            return 0.0
        q_terms = _tokenize(query)
        if not q_terms:
            return 0.0
        dl = self.doc_lengths.get(doc_id, 0)
        tf = Counter(tokens)
        total = 0.0
        for term in q_terms:
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            df = self.df.get(term, 0)
            idf = math.log(1 + (self.num_docs - df + 0.5) / (df + 0.5))
            denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avg_dl, 1))
            total += idf * (freq * (self.k1 + 1)) / max(denom, 1e-9)
        return total

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        scored = [(doc_id, self.score(query, doc_id)) for doc_id in self.doc_ids]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [(doc_id, score) for doc_id, score in scored[:top_k] if score > 0]


def _normalize_scores(scored: list[tuple[str, float]]) -> dict[str, float]:
    if not scored:
        return {}
    values = [score for _, score in scored]
    lo, hi = min(values), max(values)
    if hi <= lo:
        return {doc_id: 1.0 for doc_id, _ in scored}
    return {doc_id: (score - lo) / (hi - lo) for doc_id, score in scored}


def _query_doc_boosts(query: str) -> dict[str, float]:
    q = query.lower()
    tokens = _token_set(q)
    boosts: dict[str, float] = {}

    rules: list[tuple[set[str], dict[str, float]]] = [
        ({"health", "check", "endpoint", "curl", "api"}, {"RUNBOOK": 0.45, "RECOVERY": 0.2}),
        ({"startup", "start", "locally", "server", "shadowcast"}, {"RUNBOOK": 0.4, "RECOVERY": 0.3}),
        ({"banned", "buyer", "language", "affiliate", "commission"}, {"BUYER_LANGUAGE_RULES": 0.5, "AUDIT": 0.25}),
        ({"eval", "baseline", "prompt", "evaluation"}, {"RUNBOOK": 0.35, "AUDIT": 0.35}),
        (
            {"competitor", "comparison", "style", "vs", "content"},
            {"STYLE_RENDERING_CHECKLIST": 0.4, "MOCK_SCRIPT_EXAMPLES": 0.35, "ARCHITECTURE": 0.2},
        ),
    ]
    for trigger_tokens, doc_boosts in rules:
        if tokens & trigger_tokens:
            for doc_id, amount in doc_boosts.items():
                boosts[doc_id] = max(boosts.get(doc_id, 0.0), amount)
    return boosts


def default_rerank(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lexical reranker: boosts exact phrase, title overlap, and query-intent doc boosts."""
    q_tokens = _token_set(query)
    q_lower = query.lower()
    doc_boosts = _query_doc_boosts(query)
    reranked: list[tuple[float, dict[str, Any]]] = []
    for hit in hits:
        text = str(hit.get("text", ""))
        source = str(hit.get("source", ""))
        base = float(hit.get("score", 0))
        text_tokens = _token_set(text)
        source_tokens = _token_set(source.replace("_", " "))
        overlap = len(q_tokens & text_tokens) / max(len(q_tokens), 1)
        title_overlap = len(q_tokens & source_tokens) / max(len(q_tokens), 1)
        phrase_boost = 0.15 if q_lower[:24] in text.lower() else 0.0
        intent_boost = doc_boosts.get(source, 0.0)
        rerank_score = base + 0.25 * overlap + 0.15 * title_overlap + phrase_boost + intent_boost
        reranked.append((rerank_score, {**hit, "score": round(rerank_score, 4)}))
    reranked.sort(key=lambda item: item[0], reverse=True)
    return [hit for _, hit in reranked]


def _ollama_embed_base(base_url: str) -> str:
    root = (base_url or "http://localhost:11434/v1").rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    return root


def embed_texts(texts: list[str], base_url: str = "", model: str = DEFAULT_EMBED_MODEL) -> list[list[float]]:
    if not texts:
        return []
    root = _ollama_embed_base(base_url)
    url = f"{root}/api/embeddings"
    vectors: list[list[float]] = []
    for text in texts:
        payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            embedding = data.get("embedding")
            if isinstance(embedding, list) and embedding:
                vectors.append([float(x) for x in embedding])
                continue
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, ValueError):
            pass
        vectors.append([])
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _hybrid_score(
    query: str,
    text: str,
    *,
    query_vector: list[float],
    chunk_vector: list[float],
    bm25_score: float,
    bm25_norm: float,
) -> float:
    lexical = _lexical_score(query, text)
    dense = _cosine(query_vector, chunk_vector) if query_vector and chunk_vector else 0.0
    if query_vector and chunk_vector:
        return (
            HYBRID_DENSE_WEIGHT * dense
            + HYBRID_LEXICAL_WEIGHT * lexical
            + HYBRID_BM25_WEIGHT * bm25_norm
        )
    return 0.65 * lexical + 0.35 * bm25_norm if bm25_norm else lexical


class ResearchStore:
    """Job-scoped store for Amazon/YouTube product research snippets."""

    def __init__(self, directory: Path, *, embed_base_url: str = "", rerank_fn: Optional[RerankFn] = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.embed_base_url = embed_base_url
        self.rerank_fn = rerank_fn or default_rerank
        self.chunks_path = self.directory / "chunks.json"
        self.manifest_path = self.directory / "manifest.json"
        self.chunks: list[dict[str, Any]] = []
        if self.chunks_path.exists():
            try:
                loaded = json.loads(self.chunks_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    self.chunks = loaded
            except (OSError, json.JSONDecodeError):
                self.chunks = []

    def _add_chunks(self, texts: list[str], source: str, metadata: Optional[dict] = None) -> None:
        meta = metadata or {}
        for idx, text in enumerate(texts):
            if not text.strip():
                continue
            self.chunks.append(
                {
                    "id": f"{source}_{len(self.chunks)}_{idx}",
                    "text": text.strip(),
                    "source": source,
                    "metadata": meta,
                }
            )

    def ingest_scrape(self, scraped: dict) -> None:
        features = scraped.get("key_features") or []
        if isinstance(features, list):
            feature_text = "; ".join(str(x) for x in features)
        else:
            feature_text = str(features)
        if feature_text:
            self._add_chunks(chunk_text_sentences(feature_text), "amazon_features", {"type": "features"})

        for label, reviews in (
            ("amazon_review_positive", scraped.get("positive_reviews") or []),
            ("amazon_review_negative", scraped.get("negative_reviews") or []),
        ):
            for review in reviews[:8]:
                if not isinstance(review, dict):
                    continue
                body = f"{review.get('title', '')}: {review.get('text', '')}".strip()
                self._add_chunks(chunk_text_sentences(body), label, {"type": "review"})

    def ingest_youtube(self, research: dict) -> None:
        tags = research.get("recommended_tags") or research.get("tags") or []
        if tags:
            self._add_chunks([f"Recommended tags: {', '.join(tags[:20])}"], "youtube_tags", {"type": "tags"})
        titles = research.get("recommended_titles") or []
        for title in titles[:5]:
            self._add_chunks([str(title)], "youtube_title", {"type": "title"})
        questions = research.get("question_keywords") or []
        if questions:
            self._add_chunks(
                [f"Buyer questions: {', '.join(questions[:12])}"],
                "youtube_questions",
                {"type": "questions"},
            )

    def save(self) -> None:
        vectors = embed_texts([c["text"] for c in self.chunks], base_url=self.embed_base_url)
        for chunk, vector in zip(self.chunks, vectors):
            if vector:
                chunk["embedding"] = vector
        self.chunks_path.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")
        self.manifest_path.write_text(
            json.dumps({"chunk_count": len(self.chunks), "embedding_model": DEFAULT_EMBED_MODEL}, indent=2),
            encoding="utf-8",
        )

    def retrieve(self, query: str, top_k: int = 5, *, rerank: bool = True) -> list[dict[str, Any]]:
        if not self.chunks or not query.strip():
            return []

        query_vectors = embed_texts([query], base_url=self.embed_base_url)
        query_vector = query_vectors[0] if query_vectors else []
        bm25 = _BM25Index({c["id"]: c["text"] for c in self.chunks})
        bm25_raw = bm25.search(query, top_k=max(top_k * 3, 10))
        bm25_norm = _normalize_scores(bm25_raw)

        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in self.chunks:
            chunk_id = chunk["id"]
            vector = chunk.get("embedding") or []
            score = _hybrid_score(
                query,
                chunk.get("text", ""),
                query_vector=query_vector,
                chunk_vector=vector,
                bm25_score=bm25.score(query, chunk_id),
                bm25_norm=bm25_norm.get(chunk_id, 0.0),
            )
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, chunk in scored[: max(top_k * 2, top_k)]:
            if score <= 0:
                continue
            results.append(
                {
                    "text": chunk.get("text", ""),
                    "source": chunk.get("source", "research"),
                    "score": round(score, 3),
                    "metadata": chunk.get("metadata") or {},
                }
            )

        if rerank and results:
            results = self.rerank_fn(query, results)
        return results[:top_k]

    def retrieve_for_product(self, product_name: str) -> list[dict[str, Any]]:
        queries = [
            f"{product_name} common complaints and limitations",
            f"{product_name} praised features and strengths",
            f"{product_name} buyer questions and comparisons",
        ]
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for query in queries:
            for hit in self.retrieve(query, top_k=3):
                key = hit.get("text", "")[:120]
                if key in seen:
                    continue
                seen.add(key)
                merged.append(hit)
        return merged[:10]


class StyleCorpusStore:
    """Style-rules / docs corpus with sentence chunking and hybrid doc-level retrieval."""

    def __init__(
        self,
        corpus_dir: Path,
        *,
        embed_base_url: str = "",
        rerank_fn: Optional[RerankFn] = None,
        extra_paths: Optional[list[Path]] = None,
    ):
        self.corpus_dir = Path(corpus_dir)
        self.embed_base_url = embed_base_url
        self.rerank_fn = rerank_fn or default_rerank
        self.documents: dict[str, str] = {}
        self.chunks: list[dict[str, Any]] = []
        self._load_documents(extra_paths or [])
        self._index_chunks()
        self._bm25 = _BM25Index({c["doc_id"]: c["text"] for c in self.chunks})

    def _load_documents(self, extra_paths: list[Path]) -> None:
        paths: list[Path] = []
        if self.corpus_dir.exists():
            paths.extend(sorted(self.corpus_dir.glob("*.md")))
        paths.extend(extra_paths)
        for path in paths:
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if content:
                self.documents[path.stem] = content

    def _index_chunks(self) -> None:
        self.chunks = []
        for doc_id, content in self.documents.items():
            for idx, chunk in enumerate(chunk_text_sentences(content)):
                self.chunks.append(
                    {
                        "id": f"{doc_id}_{idx}",
                        "doc_id": doc_id,
                        "text": chunk,
                        "source": doc_id,
                    }
                )

    def retrieve_documents(self, query: str, top_k: int = 5, *, rerank: bool = True) -> list[tuple[str, float]]:
        if not query.strip() or not self.chunks:
            return []

        query_vectors = embed_texts([query], base_url=self.embed_base_url)
        query_vector = query_vectors[0] if query_vectors else []
        bm25_raw = self._bm25.search(query, top_k=max(top_k * 4, 12))
        bm25_norm = _normalize_scores(bm25_raw)

        doc_scores: dict[str, float] = {}
        for chunk in self.chunks:
            doc_id = chunk["doc_id"]
            chunk_id = chunk["id"]
            score = _hybrid_score(
                query,
                chunk["text"],
                query_vector=query_vector,
                chunk_vector=[],
                bm25_score=self._bm25.score(query, chunk_id),
                bm25_norm=bm25_norm.get(chunk_id, 0.0),
            )
            doc_scores[doc_id] = max(doc_scores.get(doc_id, 0.0), score)

        ranked = sorted(doc_scores.items(), key=lambda item: item[1], reverse=True)
        hits = [
            {
                "text": self.documents.get(doc_id, "")[:400],
                "source": doc_id,
                "score": round(score, 4),
                "metadata": {"doc_id": doc_id},
            }
            for doc_id, score in ranked[: max(top_k * 2, top_k)]
            if score > 0
        ]
        if rerank and hits:
            hits = self.rerank_fn(query, hits)
        if hits:
            top_score = float(hits[0].get("score", 0))
            threshold = max(top_score * 0.55, top_score - 0.35)
            hits = [hit for hit in hits if float(hit.get("score", 0)) >= threshold]
        return [(hit["source"], hit["score"]) for hit in hits[:top_k]]
