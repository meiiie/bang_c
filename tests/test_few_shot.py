"""Few-shot exemplars (+15.4pp evidence on Vietnamese exam MCQ) and NFC input
normalization. Config-gated, zero-shot default — the 87.26 path is unchanged.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unicodedata
import unittest
from dataclasses import replace
from pathlib import Path

from hackaithon_c.config import load_config
from hackaithon_c.loader import load_problems
from hackaithon_c.prompting import build_reasoning_prompt, load_exemplars
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem


_SHIPPED_EXEMPLARS = (
    Path(__file__).parent.parent / "src" / "hackaithon_c" / "resources" / "exemplars-vi.json"
)


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


class RecordingClient:
    model = "stub/gemma-4"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None, letters=None):
        self.prompts.append(user_prompt)
        return "ANSWER: A"


class NfcNormalizationTests(unittest.TestCase):
    def test_loader_normalizes_decomposed_vietnamese(self) -> None:
        # "tiến" written in NFD (decomposed) must load as NFC (composed).
        decomposed = unicodedata.normalize("NFD", "tiến hành kiểm tra")
        self.assertNotEqual(decomposed, "tiến hành kiểm tra")  # sanity: truly NFD
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "public_test.json"
            path.write_text(
                json.dumps(
                    [{"qid": "n1", "question": decomposed, "choices": [decomposed, "b"]}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            problem = load_problems(path)[0]
        self.assertEqual(problem.question, "tiến hành kiểm tra")
        self.assertEqual(problem.choices[0], "tiến hành kiểm tra")


class ExemplarLoadingTests(unittest.TestCase):
    def test_empty_path_means_zero_shot(self) -> None:
        self.assertEqual(load_exemplars(""), ())

    def test_shipped_exemplar_file_is_valid(self) -> None:
        exemplars = load_exemplars(str(_SHIPPED_EXEMPLARS))
        self.assertEqual(len(exemplars), 5)
        for exemplar in exemplars:
            self.assertIn(exemplar["answer"], "ABCDEFGHIJ")
            self.assertGreaterEqual(len(exemplar["choices"]), 2)
            # exemplar text must be NFC (matches normalized inputs)
            self.assertEqual(
                exemplar["question"], unicodedata.normalize("NFC", exemplar["question"])
            )

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(ValueError):
            load_exemplars(r"C:\does\not\exist\exemplars.json")


class FewShotPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.problem = Problem(
            qid="q1", question="Câu hỏi thật?", choices=("một", "hai", "ba", "bốn")
        )

    def test_zero_shot_prompt_unchanged(self) -> None:
        bundle = build_reasoning_prompt(self.problem, max_tokens=2048)
        self.assertNotIn("solved examples", bundle.user_prompt)
        self.assertIn("Câu hỏi thật?", bundle.user_prompt)

    def test_few_shot_prompt_contains_exemplars_then_real_question(self) -> None:
        exemplars = load_exemplars(str(_SHIPPED_EXEMPLARS))
        bundle = build_reasoning_prompt(self.problem, max_tokens=2048, exemplars=exemplars)
        text = bundle.user_prompt
        self.assertIn("solved examples", text)
        self.assertIn("Điện Biên Phủ", text)  # a shipped exemplar
        self.assertIn("ANSWER: C", text)  # exemplar answer line demonstrates format
        # The real question comes after the last exemplar.
        self.assertGreater(text.rfind("Câu hỏi thật?"), text.rfind("Điện Biên Phủ"))

    def test_strategy_uses_exemplars_when_configured(self) -> None:
        config = _config(
            self_consistency_samples=1,
            reasoning_few_shot_path=str(_SHIPPED_EXEMPLARS),
        )
        client = RecordingClient()
        prediction = solve_problem(self.problem, client, strategy="self_consistency", config=config)
        self.assertEqual(prediction.answer, "A")
        self.assertIn("Điện Biên Phủ", client.prompts[0])

    def test_strategy_stays_zero_shot_by_default(self) -> None:
        client = RecordingClient()
        solve_problem(self.problem, client, strategy="self_consistency", config=_config(self_consistency_samples=1))
        self.assertNotIn("solved examples", client.prompts[0])


if __name__ == "__main__":
    unittest.main()
