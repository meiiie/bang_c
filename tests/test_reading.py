"""Reading-comprehension grounding mode: passage-grounded prompt + router wiring.

The reading prompt is the passage analog of TIR (TIR grounds on executed Python
output; this grounds on a quoted passage span). The traps it must gate are the ones
observed in the real public test:
- test_0001: an option that is true but cited to the WRONG source;
- test_0003: a true fact about the subject that does not answer THIS question;
- test_0004: a plausible consequence the passage never states.
No model runs locally, so the trap gating is pinned as a PROMPT CONTRACT (the
instructions must demand quote-then-vet) and the control flow is driven with
scripted clients, mirroring test_tir.py.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from hackaithon_c.config import load_config
from hackaithon_c.prompting import build_reading_prompt
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


# "Đoạn thông tin" is a context marker -> has_long_context -> kind == "reading".
# The fixture mirrors the test_0001 trap shape: two sources, the question asks about
# ONE of them, and a distractor option is true for the OTHER source.
PASSAGE = Problem(
    qid="q_reading",
    question=(
        "Đoạn thông tin sau: Sách Đệ Nhị Luật quy định hình phạt ném đá cho tội thờ "
        "thần ngoại. Trong khi đó, sách Mishna liệt kê hình phạt ném đá cho tội phạm "
        "thượng. Câu hỏi: Theo sách Đệ Nhị Luật, tội nào bị phạt ném đá?"
    ),
    choices=["Thờ thần ngoại", "Phạm thượng", "Trộm cắp", "Khai man"],
)
# Passage AND a real computation: quantitative must win the route (the calculation
# still has to be executed even when it is stated inside a passage).
PASSAGE_CALC = Problem(
    qid="q_reading_calc",
    question=(
        "Đoạn thông tin sau: Nhà máy sản xuất 120 sản phẩm mỗi giờ và hoạt động 8 giờ "
        "mỗi ngày. Câu hỏi: Tính 120 * 8."
    ),
    choices=["960", "860", "980", "900"],
)
PROSE = Problem(
    qid="q_prose",
    question="Thủ đô của Việt Nam là thành phố nào?",
    choices=["Hà Nội", "Huế", "Đà Nẵng", "Sài Gòn"],
)
# Negative marker wins the kind ("negative" > "reading" in classifier priority), so this
# item reaches reading mode ONLY through the has_long_context feature branch of
# _is_reading — the branch that would silently disappear if it were simplified away.
NEGATIVE_PASSAGE = Problem(
    qid="q_reading_negative",
    question=(
        "Đoạn thông tin sau: Cây lúa cần nước, ánh sáng và đất phù sa để phát triển. "
        "Câu hỏi: Nhận định nào sau đây sai?"
    ),
    choices=[
        "Cây lúa cần nước",
        "Cây lúa cần ánh sáng",
        "Cây lúa cần đất phù sa",
        "Cây lúa không cần nước",
    ],
)
# CJK passages are character-dense and often stay under the long-context length
# threshold; the CJK context markers must still route them to reading mode.
CJK_PASSAGE = Problem(
    qid="q_reading_zh",
    question="阅读下面的文章:水稻需要充足的水分和阳光才能生长。问题:水稻生长需要什么?",
    choices=["水分和阳光", "只需要风", "黑暗环境", "干旱土壤"],
)


class _ScriptClient:
    """Returns one fixed response; records every prompt for routing assertions."""

    model = "stub/gemma-4"

    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []
        self.system_prompts: list[str] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None, letters=None):
        self.system_prompts.append(system_prompt)
        self.prompts.append(user_prompt)
        return self._response


class _TirClient(_ScriptClient):
    """Round 1 returns a python program, later rounds return the fixed response."""

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, **kw):
        self.system_prompts.append(system_prompt)
        self.prompts.append(user_prompt)
        if "computes the answer and prints" in user_prompt:
            return "Set up the computation.\n```python\nprint(120*8)\n```"
        return self._response


class ReadingPromptTests(unittest.TestCase):
    def test_prompt_demands_passage_quote(self) -> None:
        bundle = build_reading_prompt(PASSAGE)
        self.assertIn("Quote the exact sentence", bundle.user_prompt)
        self.assertEqual(bundle.variant, "reading")

    def test_prompt_contract_gates_wrong_source_trap(self) -> None:
        # test_0001 trap: true claim, wrong source. The contract must demand vetting
        # the attribution, not just the fact.
        bundle = build_reading_prompt(PASSAGE)
        contract = bundle.system_prompt + bundle.user_prompt
        self.assertIn("wrong source", contract)

    def test_prompt_contract_gates_off_topic_trap(self) -> None:
        # test_0003 trap: a true fact that does not answer THIS question.
        bundle = build_reading_prompt(PASSAGE)
        contract = bundle.system_prompt + bundle.user_prompt
        self.assertIn("does not answer this question", contract.lower())

    def test_prompt_contract_gates_outside_inference_trap(self) -> None:
        # test_0004 trap: a plausible consequence the passage never states.
        bundle = build_reading_prompt(PASSAGE)
        contract = bundle.system_prompt + bundle.user_prompt
        self.assertIn("the passage does not state", contract)

    def test_prompt_contract_flips_target_for_negated_questions(self) -> None:
        # NOT/except questions invert the procedure: the answer is the option the
        # passage does NOT support. The contract must say so explicitly.
        bundle = build_reading_prompt(NEGATIVE_PASSAGE)
        self.assertIn("WITHOUT support", bundle.user_prompt)

    def test_prompt_degrades_gracefully_without_passage(self) -> None:
        # The router can misfire on marker words in passage-less questions; the
        # prompt must not forbid the model from answering those from knowledge.
        bundle = build_reading_prompt(PROSE)
        self.assertIn("If no passage is supplied", bundle.user_prompt)
        self.assertIn("answer from your own knowledge", bundle.system_prompt)

    def test_prompt_checks_every_option_and_answer_format(self) -> None:
        bundle = build_reading_prompt(PASSAGE)
        self.assertIn("Check every option against the passage", bundle.user_prompt)
        self.assertIn("ANSWER: <letter>", bundle.user_prompt)
        self.assertIn("A, B, C, D", bundle.user_prompt)

    def test_prompt_includes_exemplars_before_real_question(self) -> None:
        exemplar = {
            "question": "Ví dụ: đoạn văn nói về mèo.",
            "choices": ["Mèo", "Chó"],
            "answer": "A",
        }
        bundle = build_reading_prompt(PASSAGE, exemplars=(exemplar,))
        self.assertLess(
            bundle.user_prompt.index("đoạn văn nói về mèo"),
            bundle.user_prompt.index("Đệ Nhị Luật"),
        )
        self.assertIn("Now solve the real question:", bundle.user_prompt)


class ReadingSolverTests(unittest.TestCase):
    def test_reading_votes_and_grounds_answer(self) -> None:
        client = _ScriptClient(
            'The passage states: "Sách Đệ Nhị Luật quy định hình phạt ném đá cho tội '
            'thờ thần ngoại." Option B is true of the Mishna, the wrong source. ANSWER: A'
        )
        pred = solve_problem(
            PASSAGE, client, strategy="reading", config=_config(self_consistency_samples=3)
        )
        self.assertEqual(pred.answer, "A")
        self.assertEqual(pred.strategy, "gemma_reading")
        self.assertEqual(pred.prompt_variant, "reading")
        self.assertEqual(pred.attempts, 3)
        actions = [step.action for step in pred.trace]
        self.assertTrue(any(action.startswith("reading_sample") for action in actions))

    def test_reading_samples_use_the_reading_prompt(self) -> None:
        client = _ScriptClient("ANSWER: A")
        solve_problem(PASSAGE, client, strategy="reading", config=_config(self_consistency_samples=2))
        self.assertTrue(all("Quote the exact sentence" in p for p in client.prompts))
        self.assertTrue(all("supplied passage" in s for s in client.system_prompts))

    def test_reading_falls_back_when_no_valid_letter(self) -> None:
        client = _ScriptClient("I cannot decide between the options.")
        pred = solve_problem(
            PASSAGE, client, strategy="reading", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.fallback_reason, "invalid_reading")
        self.assertIn(pred.answer, PASSAGE.allowed_letters)


class RouterTests(unittest.TestCase):
    def test_router_sends_passage_to_reading_mode(self) -> None:
        client = _ScriptClient("Grounded in the passage. ANSWER: A")
        pred = solve_problem(
            PASSAGE, client, strategy="router", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_reading")
        self.assertTrue(any("Quote the exact sentence" in p for p in client.prompts))
        # reading mode must NOT ask for python code
        self.assertFalse(any("```python" in p for p in client.prompts))

    def test_router_routes_negative_passage_to_reading(self) -> None:
        # Pins the feature branch of _is_reading: kind is "negative" here, so only
        # the has_long_context check sends this trap-heavy item to reading mode.
        client = _ScriptClient("ANSWER: D")
        pred = solve_problem(
            NEGATIVE_PASSAGE, client, strategy="router", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_reading")
        self.assertTrue(any("Quote the exact sentence" in p for p in client.prompts))

    def test_router_routes_cjk_passage_to_reading(self) -> None:
        client = _ScriptClient("ANSWER: A")
        pred = solve_problem(
            CJK_PASSAGE, client, strategy="router", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_reading")

    def test_router_quantitative_wins_over_passage(self) -> None:
        client = _TirClient("The result 960 matches. ANSWER: A")
        pred = solve_problem(
            PASSAGE_CALC, client, strategy="router", config=_config(tir_samples=1)
        )
        self.assertTrue(pred.strategy.startswith("gemma_tir"))
        self.assertTrue(any("prints the final numeric result" in p for p in client.prompts))

    def test_router_prose_still_goes_to_self_consistency(self) -> None:
        client = _ScriptClient("Hà Nội is the capital. ANSWER: A")
        pred = solve_problem(
            PROSE, client, strategy="router", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_self_consistency")
        self.assertFalse(any("Quote the exact sentence" in p for p in client.prompts))

    def test_reading_strategy_forces_mode_for_measurement(self) -> None:
        # Per-bucket measurement on a reading proxy must not depend on classifier
        # recall: strategy="reading" forces the mode even on a short prose item.
        client = _ScriptClient("ANSWER: A")
        pred = solve_problem(
            PROSE, client, strategy="reading", config=_config(self_consistency_samples=1)
        )
        self.assertEqual(pred.strategy, "gemma_reading")


class ConfigTests(unittest.TestCase):
    def test_reading_workflow_registered_off_default(self) -> None:
        config = load_config()
        workflow = config.workflows["reading"]
        self.assertEqual(workflow["strategy"], "reading")
        self.assertEqual(workflow["phase"], "development")
        # the contest default path must remain self-consistency
        self.assertEqual(config.workflows["self-consistency"]["phase"], "runtime")


if __name__ == "__main__":
    unittest.main()
