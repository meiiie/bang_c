from __future__ import annotations

import json
import math
import re
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Snippet:
    doc_id: str
    title: str
    text: str
    score: float


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with DIACRITICS KEPT.

    Vietnamese diacritics are meaning-bearing (tỉnh/tính/tinh are different words);
    stripping marks for matching collapses them — see notes/lessons.md 2026-06-10.
    \\w is Unicode-aware, so this works unchanged for any language in the corpus.
    """
    return re.findall(r"\w+", text.lower())


class BM25Retriever:
    """In-memory Okapi BM25 over {id, title, text} documents.

    Standard library only: the contest runtime must stay offline and dependency-free.
    k1/b are the universal literature defaults, not tuned to any test set. Scoring is
    sparse (postings of query tokens only), so corpora of a few hundred thousand
    chunks stay fast enough for a one-time index build at startup.
    """

    def __init__(self, documents: list[dict], *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._documents = documents
        self._doc_lengths: list[int] = []
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for index, document in enumerate(documents):
            tokens = tokenize(f"{document.get('title', '')} {document['text']}")
            self._doc_lengths.append(len(tokens))
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token, count in counts.items():
                self._postings.setdefault(token, []).append((index, count))
        total_length = sum(self._doc_lengths)
        self._avg_length = total_length / len(documents) if documents else 0.0

    def __len__(self) -> int:
        return len(self._documents)

    def retrieve(self, query: str, top_k: int = 4) -> list[Snippet]:
        if not self._documents:
            return []
        scores: dict[int, float] = {}
        doc_count = len(self._documents)
        # sorted(): set iteration order is hash-randomized per process, and float
        # accumulation is non-associative — sorting keeps scores bit-reproducible
        # across runs (the same guarantee stable_seed gives sampling elsewhere).
        for token in sorted(set(tokenize(query))):
            postings = self._postings.get(token)
            if not postings:
                continue
            df = len(postings)
            # Skip tokens present in over a third of the corpus: function words in
            # any language, near-zero idf, and their postings scans dominate query
            # latency on a 344k-chunk corpus (~3x measured scan reduction).
            if df > max(1, doc_count // 3):
                continue
            idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
            for index, tf in postings:
                length_norm = 1.0 - self._b + self._b * (
                    self._doc_lengths[index] / self._avg_length
                )
                scores[index] = scores.get(index, 0.0) + idf * (
                    tf * (self._k1 + 1.0) / (tf + self._k1 * length_norm)
                )
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        snippets = []
        for index, score in ranked[: max(1, top_k)]:
            document = self._documents[index]
            snippets.append(
                Snippet(
                    doc_id=str(document.get("id", index)),
                    title=str(document.get("title", "")),
                    text=str(document["text"]),
                    score=score,
                )
            )
        return snippets


def load_retriever(path: str) -> BM25Retriever:
    """Load a JSONL corpus ({id, title, text} per line) into a BM25 index."""
    corpus_path = Path(path)
    documents: list[dict] = []
    with corpus_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or "text" not in row:
                raise ValueError(
                    f"Corpus line {line_number} must be an object with a 'text' field: {corpus_path}"
                )
            documents.append(row)
    if not documents:
        raise ValueError(f"Corpus is empty: {corpus_path}")
    return BM25Retriever(documents)


_cache: dict[str, BM25Retriever | Exception] = {}
_cache_lock = threading.Lock()


def cached_retriever(path: str) -> BM25Retriever:
    """One index per corpus path per process, thread-safe.

    Not lru_cache, deliberately: (a) lru_cache does not deduplicate concurrent
    first calls, so N worker threads hitting a cold cache would each run the
    ~70s multi-GB index build; (b) it does not memoize failures, so a corrupt
    corpus would be re-parsed in full on every RAG-routed question. The lock is
    held across the build — concurrent callers wait for one build instead of
    duplicating it — and a load failure is remembered and re-raised cheaply.
    """
    with _cache_lock:
        cached = _cache.get(path)
        if cached is None:
            try:
                cached = load_retriever(path)
            except Exception as error:  # noqa: BLE001 - remember any load failure
                cached = error
            _cache[path] = cached
    if isinstance(cached, Exception):
        raise cached
    return cached
