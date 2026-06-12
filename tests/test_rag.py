"""Targeted RAG: offline BM25 retrieval + retrieval-grounded prompt + router gating.

The retriever is exercised for real (BM25 over a fixture corpus, diacritics kept);
the solver control flow runs with scripted clients, mirroring test_tir/test_reading.
The hard guarantees pinned here:
- RAG is OFF by default: with no rag_corpus_path the router NEVER fires it.
- Excerpts are fallible references — the prompt must let the model fall back to its
  own knowledge (the level-2 review lesson about misroute harm).
- A retrieval miss or broken corpus degrades to self-consistency; pred.csv complete.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from unittest import mock

from hackaithon_c.config import load_config
from hackaithon_c.prompting import build_rag_prompt
from hackaithon_c.retrieval import BM25Retriever, Snippet, cached_retriever, load_retriever, tokenize
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


CORPUS_DOCS = [
    {
        "id": "cccd-19",
        "title": "Luật Căn cước — Điều 19",
        "text": (
            "Công dân làm thủ tục cấp thẻ căn cước tại cơ quan quản lý căn cước "
            "cấp tỉnh hoặc cấp huyện; hồ sơ gồm phiếu thu nhận thông tin và giấy tờ "
            "chứng minh nơi cư trú."
        ),
    },
    {
        "id": "pccc-12",
        "title": "Luật Phòng cháy chữa cháy — Điều 12",
        "text": (
            "Thiết kế phòng cháy và chữa cháy của công trình phải được cơ quan "
            "Cảnh sát phòng cháy và chữa cháy thẩm duyệt trước khi thi công."
        ),
    },
    {
        "id": "tinh-vs-tinh",
        "title": "Đơn vị hành chính",
        "text": "Tỉnh là đơn vị hành chính cấp cao nhất ở địa phương của Việt Nam.",
    },
    {
        "id": "toan-hoc",
        "title": "Phép tính",
        "text": "Tính tổng của một dãy số là cộng tất cả các phần tử của dãy.",
    },
]

LEGAL = Problem(
    qid="q_legal",
    question="Công dân làm thủ tục cấp thẻ căn cước cần nộp hồ sơ tại cơ quan nào?",
    choices=[
        "Cơ quan quản lý căn cước cấp tỉnh hoặc cấp huyện",
        "Bộ Ngoại giao",
        "Trường đại học",
        "Ngân hàng thương mại",
    ],
)
PROSE = Problem(
    qid="q_prose",
    question="Thủ đô của Việt Nam là thành phố nào?",
    choices=["Hà Nội", "Huế", "Đà Nẵng", "Sài Gòn"],
)


def _write_corpus(directory: str, docs=CORPUS_DOCS) -> str:
    path = Path(directory) / "corpus.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return str(path)


class _ScriptClient:
    model = "stub/gemma-4"

    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []
        self.system_prompts: list[str] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None, letters=None):
        self.system_prompts.append(system_prompt)
        self.prompts.append(user_prompt)
        return self._response


class RetrieverTests(unittest.TestCase):
    def test_tokenizer_keeps_diacritics(self) -> None:
        # The hard pin for the "keep Vietnamese diacritics" rule: a stripping
        # tokenizer collapses all three words to "tinh" (mutation-verified — the
        # ranking tests below survive that mutation, this assertion does not).
        self.assertEqual(tokenize("Tỉnh tính tinh"), ["tỉnh", "tính", "tinh"])

    def test_retrieves_matching_statute_first(self) -> None:
        retriever = BM25Retriever(CORPUS_DOCS)
        snippets = retriever.retrieve("thủ tục cấp thẻ căn cước", top_k=2)
        self.assertEqual(snippets[0].doc_id, "cccd-19")

    def test_diacritics_distinguish_tokens(self) -> None:
        # "tỉnh" (province) and "tính" (compute) must NOT collapse: a query about
        # provinces must rank the province doc above the arithmetic doc.
        retriever = BM25Retriever(CORPUS_DOCS)
        snippets = retriever.retrieve("tỉnh là đơn vị hành chính", top_k=1)
        self.assertEqual(snippets[0].doc_id, "tinh-vs-tinh")
        snippets = retriever.retrieve("tính tổng dãy số", top_k=1)
        self.assertEqual(snippets[0].doc_id, "toan-hoc")

    def test_no_overlap_returns_empty(self) -> None:
        retriever = BM25Retriever(CORPUS_DOCS)
        self.assertEqual(retriever.retrieve("quantum chromodynamics"), [])

    def test_top_k_respected(self) -> None:
        retriever = BM25Retriever(CORPUS_DOCS)
        snippets = retriever.retrieve("phòng cháy chữa cháy căn cước tỉnh", top_k=2)
        self.assertEqual(len(snippets), 2)

    def test_load_retriever_roundtrip_and_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            retriever = load_retriever(path)
            self.assertEqual(len(retriever), len(CORPUS_DOCS))
            bad = Path(directory) / "bad.jsonl"
            bad.write_text('{"title": "no text field"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_retriever(str(bad))
            with self.assertRaises(OSError):
                load_retriever(str(Path(directory) / "missing.jsonl"))

    def test_cached_retriever_builds_once_and_memoizes_failure(self) -> None:
        # The 344k-chunk index build costs ~70s and ~2.5GB: concurrent first
        # callers must share ONE build, and a broken corpus must fail once, not
        # be re-parsed on every RAG-routed question.
        calls = {"count": 0}
        real = load_retriever

        def counting(path):
            calls["count"] += 1
            return real(path)

        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            with mock.patch("hackaithon_c.retrieval.load_retriever", counting):
                first = cached_retriever(path)
                second = cached_retriever(path)
            self.assertIs(first, second)
            self.assertEqual(calls["count"], 1)

            broken = Path(directory) / "broken.jsonl"
            broken.write_text("not json\n", encoding="utf-8")
            with mock.patch("hackaithon_c.retrieval.load_retriever", counting):
                for _ in range(2):
                    with self.assertRaises(ValueError):
                        cached_retriever(str(broken))
            self.assertEqual(calls["count"], 2)  # one success + ONE failed attempt


class RagPromptTests(unittest.TestCase):
    def _snippets(self):
        return (
            Snippet(doc_id="cccd-19", title="Luật Căn cước — Điều 19", text="Công dân làm thủ tục...", score=5.0),
        )

    def test_prompt_includes_references_and_answer_format(self) -> None:
        bundle = build_rag_prompt(LEGAL, self._snippets())
        self.assertIn("Luật Căn cước — Điều 19", bundle.user_prompt)
        self.assertIn("ANSWER: <letter>", bundle.user_prompt)
        self.assertEqual(bundle.variant, "rag")

    def test_prompt_treats_excerpts_as_fallible(self) -> None:
        # The level-2 lesson: a grounding prompt must never suppress the model's own
        # knowledge when the grounding material misses.
        bundle = build_rag_prompt(LEGAL, self._snippets())
        self.assertIn("may be irrelevant", bundle.user_prompt)
        self.assertIn("otherwise use your own knowledge", bundle.user_prompt)
        self.assertIn("rely on your own knowledge", bundle.system_prompt)

    def test_prompt_caps_snippet_length_with_visible_marker(self) -> None:
        # Cap matches the corpus-build chunk size (1500) and the cut must be
        # VISIBLE: the model has to distinguish a truncated excerpt from a
        # complete short article.
        long_snippet = Snippet(doc_id="x", title="T", text="word " * 1000, score=1.0)
        bundle = build_rag_prompt(LEGAL, (long_snippet,))
        self.assertNotIn("word " * 320, bundle.user_prompt)
        self.assertIn("[…]", bundle.user_prompt)
        short_snippet = Snippet(doc_id="y", title="T", text="ngắn gọn", score=1.0)
        bundle = build_rag_prompt(LEGAL, (short_snippet,))
        self.assertNotIn("[…]", bundle.user_prompt)


class RagSolverTests(unittest.TestCase):
    def test_rag_retrieves_and_grounds_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("Điều 19 nói rõ cơ quan cấp tỉnh hoặc cấp huyện. ANSWER: A")
            pred = solve_problem(
                LEGAL,
                client,
                strategy="rag",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.answer, "A")
            self.assertEqual(pred.strategy, "gemma_rag")
            self.assertEqual(pred.prompt_variant, "rag")
            retrieve_steps = [s for s in pred.trace if s.role == "rag"]
            self.assertTrue(any("cccd-19" in s.detail for s in retrieve_steps))
            self.assertTrue(any("Reference excerpts" in p for p in client.prompts))

    def test_rag_without_corpus_degrades_to_self_consistency(self) -> None:
        client = _ScriptClient("ANSWER: A")
        pred = solve_problem(
            LEGAL, client, strategy="rag", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        warnings = [s for s in pred.trace if s.role == "rag" and s.status == "warning"]
        self.assertTrue(any("no corpus configured" in s.detail for s in warnings))

    def test_rag_no_snippets_matched_degrades_to_self_consistency(self) -> None:
        # Corpus loads fine but the query shares no tokens with it: must degrade
        # with a warning, never build a RAG prompt around an empty references block.
        english = Problem(
            qid="q_english",
            question="Which planet is known as the red planet?",
            choices=["Mars", "Venus", "Jupiter", "Saturn"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("ANSWER: A")
            pred = solve_problem(
                english,
                client,
                strategy="rag",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.strategy, "gemma_self_consistency")
            warnings = [s for s in pred.trace if s.role == "rag" and s.status == "warning"]
            self.assertTrue(any("no snippets matched" in s.detail for s in warnings))
            self.assertFalse(any("Reference excerpts" in p for p in client.prompts))

    def test_rag_with_broken_corpus_degrades_not_crashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "broken.jsonl"
            bad.write_text("not json at all\n", encoding="utf-8")
            client = _ScriptClient("ANSWER: B")
            pred = solve_problem(
                LEGAL,
                client,
                strategy="rag",
                config=_config(rag_corpus_path=str(bad), self_consistency_samples=1),
            )
            self.assertEqual(pred.answer, "B")
            self.assertEqual(pred.strategy, "gemma_self_consistency")
            warnings = [s for s in pred.trace if s.role == "rag" and s.status == "warning"]
            self.assertTrue(any("retrieval_error" in s.detail for s in warnings))


class RouterTests(unittest.TestCase):
    def test_router_never_fires_rag_without_corpus(self) -> None:
        # The hard OFF-by-default guarantee: default config has rag_corpus_path="".
        client = _ScriptClient("ANSWER: A")
        pred = solve_problem(
            LEGAL, client, strategy="router", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        self.assertFalse(any("Reference excerpts" in p for p in client.prompts))
        # The router must not even ENTER rag mode (mutation-verified: without this,
        # dropping the corpus-path guard survives — the degrade path masks it).
        self.assertFalse(any(s.role == "rag" for s in pred.trace))

    def test_router_single_polysemous_marker_does_not_fire_rag(self) -> None:
        # "cơ quan" (biology: organ) and "cấp tính" (medicine: acute) hit single
        # legal markers after diacritic stripping; one marker must NOT route a
        # non-legal question into legal-statute retrieval.
        biology = Problem(
            qid="q_biology",
            question="Cơ quan nào của cây thực hiện quá trình quang hợp?",
            choices=["Lá cây", "Rễ cây", "Thân cây", "Hoa"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("ANSWER: A")
            pred = solve_problem(
                biology,
                client,
                strategy="router",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.strategy, "gemma_self_consistency")
            self.assertFalse(any(s.role == "rag" for s in pred.trace))

    def test_router_routes_legal_to_rag_when_corpus_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("ANSWER: A")
            pred = solve_problem(
                LEGAL,
                client,
                strategy="router",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.strategy, "gemma_rag")

    def test_router_non_legal_prose_stays_self_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("ANSWER: A")
            pred = solve_problem(
                PROSE,
                client,
                strategy="router",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.strategy, "gemma_self_consistency")

    def test_router_reading_wins_over_rag(self) -> None:
        # A legal question WITH a supplied passage: the text is given, so reading
        # grounding beats retrieval (router order pinned).
        passage_legal = Problem(
            qid="q_passage_legal",
            question=(
                "Đoạn thông tin sau: Theo Điều 19, công dân làm thủ tục cấp thẻ căn cước "
                "tại cơ quan quản lý căn cước cấp tỉnh hoặc cấp huyện. "
                "Câu hỏi: Công dân nộp hồ sơ ở đâu?"
            ),
            choices=["Cấp tỉnh hoặc cấp huyện", "Bộ Ngoại giao", "Trường học", "Bệnh viện"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = _write_corpus(directory)
            client = _ScriptClient("ANSWER: A")
            pred = solve_problem(
                passage_legal,
                client,
                strategy="router",
                config=_config(rag_corpus_path=path, self_consistency_samples=1),
            )
            self.assertEqual(pred.strategy, "gemma_reading")


class ConfigTests(unittest.TestCase):
    def test_rag_workflow_registered_off_default(self) -> None:
        config = load_config()
        self.assertEqual(config.workflows["rag"]["strategy"], "rag")
        self.assertEqual(config.workflows["rag"]["phase"], "development")
        self.assertEqual(config.rag_corpus_path, "")
        self.assertEqual(config.workflows["self-consistency"]["phase"], "runtime")


if __name__ == "__main__":
    unittest.main()
