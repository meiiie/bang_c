"""Agreement-based confidence calibration.

Replaces hard-coded per-code-path confidence constants with a real, observable signal:
how much repeated reasoning samples agree on the same answer. Unanimous -> 1.0, an even
split -> 0.5, and so on. This makes risk review meaningful and lets the harness spend
extra compute only on genuinely uncertain items.

Pure functions, no model calls — fully deterministic and unit-testable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def majority_vote(answers: Sequence[str]) -> tuple[str | None, int, int]:
    """Return (winner, winner_votes, total_valid).

    Only non-empty answers count as valid votes. Ties are broken by **first
    appearance** in sample order — deterministic and not alphabet-biased (so it never
    silently favours 'A'). A genuine tie still surfaces as a low agreement score, which
    is the signal an escalation step should act on.
    """
    valid = [answer for answer in answers if answer]
    if not valid:
        return None, 0, 0
    counts = Counter(valid)
    top_votes = max(counts.values())
    winner = next(answer for answer in valid if counts[answer] == top_votes)
    return winner, top_votes, len(valid)


def agreement_confidence(winner_votes: int, total_valid: int) -> float:
    """Calibrated confidence = fraction of valid samples that agreed on the winner."""
    if total_valid <= 0:
        return 0.0
    return winner_votes / total_valid


def vote_distribution(answers: Sequence[str]) -> str:
    """Human-readable distribution like 'A:3,B:1' over valid answers, sorted by letter."""
    counts = Counter(answer for answer in answers if answer)
    return ",".join(f"{letter}:{counts[letter]}" for letter in sorted(counts))
