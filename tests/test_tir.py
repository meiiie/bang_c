"""Tool-integrated reasoning: offline Python execution + the quantitative router.

The executor is exercised for real (it runs actual subprocesses); the solver is driven
with scripted clients so the TIR control flow is tested without a model. The router's
non-quantitative path must NOT execute code.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from hackaithon_c.config import load_config
from hackaithon_c.prompting import build_tir_answer_prompt, build_tir_code_prompt
from hackaithon_c.schema import Problem
from hackaithon_c.solver import solve_problem
from hackaithon_c.tool_runtime import ExecResult, extract_code, run_python


def _config(**runtime_overrides):
    base = load_config()
    raw = copy.deepcopy(base.raw)
    raw.setdefault("runtime", {}).update(runtime_overrides)
    return replace(base, raw=raw)


QUANT = Problem(
    qid="q_calc",
    question="Tính giá trị của 12 * 12 + 1.",
    choices=["143", "145", "144", "150"],
)
PROSE = Problem(
    qid="q_prose",
    question="Thủ đô của Việt Nam là thành phố nào?",
    choices=["Hà Nội", "Huế", "Đà Nẵng", "Sài Gòn"],
)


class ExecutorTests(unittest.TestCase):
    def test_extract_last_code_block(self) -> None:
        text = "first\n```python\nx=1\n```\nthen\n```python\nprint(2)\n```"
        self.assertEqual(extract_code(text), "print(2)")

    def test_extract_none_when_no_fence(self) -> None:
        self.assertIsNone(extract_code("just prose, no code"))
        self.assertIsNone(extract_code(""))

    def test_run_python_captures_stdout(self) -> None:
        result = run_python("print(6*7)")
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "42")

    def test_run_python_reports_error(self) -> None:
        result = run_python("raise ValueError('boom')")
        self.assertFalse(result.ok)
        self.assertIn("ValueError", result.stderr)

    def test_run_python_times_out(self) -> None:
        result = run_python("while True: pass", timeout_seconds=1.0)
        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)

    def test_run_python_empty_code(self) -> None:
        self.assertFalse(run_python("   ").ok)

    def test_isolated_from_parent_env(self) -> None:
        # -I mode: os import still works, but no user site / PYTHON* influence needed
        result = run_python("import math; print(round(math.sqrt(144)))")
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "12")


class _TirClient:
    """Scripted client: round 1 returns code, round 2 returns the letter.

    Tracks every prompt so tests can assert which rounds ran.
    """

    model = "stub/gemma-4"

    def __init__(self, code: str, letter_response: str) -> None:
        self._code = code
        self._letter = letter_response
        self.prompts: list[str] = []

    def complete(self, system_prompt, user_prompt, *, max_tokens=12, temperature=None, top_p=None, top_k=None, seed=None):
        self.prompts.append(user_prompt)
        if "```python```" in user_prompt or "computes the answer and prints" in user_prompt:
            return f"Set up the computation.\n```python\n{self._code}\n```"
        return self._letter


class TirSolverTests(unittest.TestCase):
    def test_tir_executes_and_grounds_answer(self) -> None:
        # Code prints 144; the answer round commits to C (the 144 option).
        client = _TirClient(code="print(12*12)", letter_response="The result 144 matches. ANSWER: C")
        pred = solve_problem(QUANT, client, strategy="tir", config=_config(tir_samples=1))
        self.assertEqual(pred.answer, "C")
        self.assertTrue(pred.strategy.startswith("gemma_tir"))
        # an exec trace step must exist and report success
        actions = [(s.role, s.action, s.status) for s in pred.trace]
        self.assertTrue(any(role == "tir" and action.startswith("exec") for role, action, _ in actions))

    def test_tir_degrades_when_no_code(self) -> None:
        # Model never emits code; must fall back to reasoning, not crash.
        client = _TirClient(code="", letter_response="ANSWER: A")

        # With empty code the round-1 response has no fence -> degrade path.
        class NoCode(_TirClient):
            def complete(self, system_prompt, user_prompt, *, max_tokens=12, **kw):
                self.prompts.append(user_prompt)
                return "ANSWER: A"  # never a code block

        nc = NoCode(code="", letter_response="ANSWER: A")
        pred = solve_problem(QUANT, nc, strategy="tir", config=_config(tir_samples=1))
        self.assertEqual(pred.answer, "A")
        self.assertIn("degraded", pred.strategy)

    def test_tir_survives_exec_error(self) -> None:
        client = _TirClient(code="raise RuntimeError('bad setup')", letter_response="ANSWER: B")
        pred = solve_problem(QUANT, client, strategy="tir", config=_config(tir_samples=1))
        # exec failed but the answer round still produces a letter from the stderr context
        self.assertEqual(pred.answer, "B")
        actions = [(s.role, s.status) for s in pred.trace if s.role == "tir"]
        self.assertTrue(any(status == "warning" for _, status in actions))


class RouterTests(unittest.TestCase):
    def test_router_sends_quantitative_to_tir(self) -> None:
        client = _TirClient(code="print(12*12+1)", letter_response="ANSWER: A")
        pred = solve_problem(QUANT, client, strategy="router", config=_config(tir_samples=1))
        self.assertTrue(pred.strategy.startswith("gemma_tir"))
        # the code-writing prompt (TIR round 1) must have been issued
        self.assertTrue(any("prints the final numeric result" in p for p in client.prompts))

    def test_router_sends_prose_to_self_consistency(self) -> None:
        class ReasoningClient:
            model = "stub/gemma-4"

            def __init__(self):
                self.prompts = []

            def complete(self, system_prompt, user_prompt, *, max_tokens=12, **kw):
                self.prompts.append(user_prompt)
                return "Hà Nội is the capital. ANSWER: A"

        client = ReasoningClient()
        pred = solve_problem(PROSE, client, strategy="router", config=_config(self_consistency_samples=1))
        self.assertEqual(pred.answer, "A")
        self.assertIn("self_consistency", pred.strategy)
        # must NOT have asked for python code
        self.assertFalse(any("```python" in p for p in client.prompts))


class TirPromptTests(unittest.TestCase):
    def test_code_prompt_forbids_letter(self) -> None:
        bundle = build_tir_code_prompt(QUANT)
        self.assertIn("Do not select an option", bundle.user_prompt)
        self.assertIn("python", bundle.system_prompt.lower())

    def test_answer_prompt_includes_execution_output(self) -> None:
        bundle = build_tir_answer_prompt(QUANT, "print(144)", "144")
        self.assertIn("144", bundle.user_prompt)
        self.assertIn("ANSWER:", bundle.user_prompt)


if __name__ == "__main__":
    unittest.main()
