"""Choice-order permutation for position-bias debiasing.

LLMs are not robust multiple-choice selectors: the same question with reordered
choices can flip the answer (selection/position bias). Asking the model several
times with cyclically rotated choice orders and voting in the ORIGINAL letter
space cancels that bias. Rotations are deterministic, so runs stay reproducible.

Pure functions, no model calls.
"""

from __future__ import annotations

import hashlib

from .schema import Problem


def rotation_for_sample(sample_index: int, n_choices: int) -> int:
    """Deterministic rotation for the i-th diversified sample.

    Sample 0 is the un-permuted anchor. Samples 1.. cycle through the n-1
    non-identity rotations so consecutive samples see different orders.
    """
    if sample_index <= 0 or n_choices < 2:
        return 0
    return 1 + (sample_index - 1) % (n_choices - 1)


def rotate_problem(problem: Problem, rotation: int) -> Problem:
    """Return the problem with choices cyclically rotated by `rotation`.

    rotated_choices[j] = choices[(j + rotation) % n], qid/question unchanged.
    """
    n = len(problem.choices)
    if n < 2 or rotation % n == 0:
        return problem
    rotated = tuple(problem.choices[(j + rotation) % n] for j in range(n))
    return Problem(qid=problem.qid, question=problem.question, choices=rotated)


def original_letter(rotated_answer: str, rotation: int, problem: Problem) -> str | None:
    """Map an answer letter given in rotated-choice space back to the original letter."""
    n = len(problem.choices)
    letters = problem.allowed_letters
    j = letters.find(rotated_answer)
    if j < 0:
        return None
    if n < 2 or rotation % n == 0:
        return rotated_answer
    return letters[(j + rotation) % n]


def stable_seed(qid: str, sample_index: int) -> int:
    """Deterministic 32-bit seed per (question, sample) so temperature>0 sampling is
    reproducible across runs (Python's hash() is randomized per process — not used)."""
    digest = hashlib.sha256(f"{qid}|{sample_index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")
