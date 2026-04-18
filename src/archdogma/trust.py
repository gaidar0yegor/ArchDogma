"""Trust Score — how much we believe the code does what it claims.

v0.1 scope (see README):
    Verifiable signals only — code age, test coverage, complexity.
    No "expert" numbers pulled from nowhere.

ADR-003 (pending) will formalize the formula: inputs, weights, normalization.

This module is a skeleton. Do not use yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustScore:
    """Trust Score result.

    Score is in [0.0, 1.0]. Reasons is an ordered list of contributing
    factors, each with its own sub-score — so the final number can always
    be traced back to verifiable signals.
    """

    score: float
    reasons: tuple[tuple[str, float], ...]


def compute(**signals: float) -> TrustScore:
    """Compute a Trust Score from verified signals.

    Pending ADR-003. Right now this just raises — better than returning
    a number that looks authoritative but is actually made up.
    """
    raise NotImplementedError(
        "Trust Score formula not finalized. See ADR-003 (pending)."
    )
