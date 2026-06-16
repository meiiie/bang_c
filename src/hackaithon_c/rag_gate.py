"""Dense cross-encoder relevance gate for the targeted-RAG route.

The marker/BM25 gate is lexical: it fires on word overlap, so physics and
Ho-Chi-Minh-thought questions that merely share common Vietnamese tokens
(cấp/phương/tỉnh) score as high as the genuine current-fact questions, and
always-on injection nets negative (notes/rag-oracle-dev-2026-06-15). A
cross-encoder judges *semantic* relevance of the question to a corpus chunk, so
those lexical false-positives collapse to ~0 while the real current-fact
questions stay near 1.0 — a clean separation on the dev pool
(notes/rag-dense-gate-2026-06-15).

Two interchangeable backends, both OPTIONAL and imported lazily so the default
stdlib path never touches either:

- ``"llamacpp"`` (ship): a BGE-reranker GGUF run through the SAME llama-cpp-python
  the container already uses for Gemma (``pooling_type=RANK``). No torch -> stays
  portable (GGML_NATIVE=off); torch CPU wheels need AVX and SIGILL on old contest
  CPUs. Verified on a GGML_NATIVE=off build: reform questions score logit ~+5..+7,
  off-topic ~-9..-11 (delta ~+16), i.e. sigmoid ~0.996 vs ~0.
- ``"transformers"`` (dev/eval): the torch cross-encoder used to dev-validate the
  gate offline. Heavier, not shipped.

If the chosen backend or model is unavailable for any reason the gate returns
``None`` and the caller degrades to RAG-off, never crashing — the per-question
bulletproof contract is preserved.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass


def _sigmoid(value: float) -> float:
    # Numerically stable; reranker logits span roughly [-12, +8].
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


@dataclass(frozen=True)
class _TransformersReranker:
    tokenizer: object
    model: object

    def score(self, query: str, documents: list[str], max_length: int) -> float:
        import torch

        device = next(self.model.parameters()).device
        pairs = [[query, document] for document in documents]
        encoded = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            logits = self.model(**encoded).logits.view(-1).float()
            relevance = torch.sigmoid(logits)
        return float(relevance.max().item())


@dataclass(frozen=True)
class _LlamaReranker:
    model: object

    def score(self, query: str, documents: list[str], max_length: int) -> float:
        # llama.cpp applies the reranker's own formatting under RANK pooling; any
        # plain query+document concatenation yields the same score (verified), so a
        # tab join is enough. create_embedding returns the rank logit as the first
        # (only) embedding value; sigmoid maps it to the [0,1] gate scale.
        best = 0.0
        for document in documents:
            result = self.model.create_embedding(f"{query}\t{document}")
            embedding = result["data"][0]["embedding"]
            logit = float(embedding[0] if isinstance(embedding, list) else embedding)
            best = max(best, _sigmoid(logit))
        return best


def _load_transformers(model_name: str, **_kwargs) -> _TransformersReranker:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
    if torch.cuda.is_available():
        model = model.to("cuda")
    return _TransformersReranker(tokenizer=tokenizer, model=model)


def _load_llamacpp(model_path: str, *, n_ctx: int, n_gpu_layers: int) -> _LlamaReranker:
    import llama_cpp
    from llama_cpp import Llama

    model = Llama(
        model_path=model_path,
        embedding=True,
        pooling_type=llama_cpp.LLAMA_POOLING_TYPE_RANK,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )
    return _LlamaReranker(model=model)


# (backend, model_ref) -> loaded reranker OR the load Exception (memoized so a missing
# model is not retried per question). Same failure-memoizing pattern as cached_retriever.
_cache: dict[tuple[str, str], object] = {}
_cache_lock = threading.Lock()


def _get(backend: str, model_ref: str, **load_kwargs) -> object:
    key = (backend, model_ref)
    with _cache_lock:
        cached = _cache.get(key)
        if cached is None:
            try:
                if backend == "transformers":
                    cached = _load_transformers(model_ref)
                else:
                    cached = _load_llamacpp(model_ref, **load_kwargs)
            except Exception as error:  # noqa: BLE001 - any import/load failure -> gate off
                cached = error
            _cache[key] = cached
    return cached


def reranker_relevance(
    model_ref: str,
    query: str,
    documents: list[str],
    *,
    backend: str = "llamacpp",
    max_length: int = 512,
    n_ctx: int = 2048,
    n_gpu_layers: int = -1,
) -> float | None:
    """Max relevance of ``query`` over ``documents`` in [0, 1].

    Returns ``None`` when no model is configured, there are no documents, or the
    optional backend is unavailable — the caller treats ``None`` as "do not fire
    RAG" so a missing dependency degrades safely instead of raising.
    """
    if not model_ref or not documents:
        return None
    reranker = _get(backend, model_ref, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
    if isinstance(reranker, Exception):
        return None
    try:
        return reranker.score(query, documents, max_length)
    except Exception:  # noqa: BLE001 - a scoring failure must not break the run
        return None
