"""Dependency-resilience: the ``waiting`` state for busy/asleep external services.

When a step hits an external dependency that is only *temporarily* unavailable —
the ai_tools GPU node (OCR / anonymisation) suspended or busy, or a transient
LLM / adapter outage — the pipeline must **not** fail. The dependency call raises
:class:`DependencyUnavailable`; ``tracked_run`` then drives the run to ``waiting``
(machine code + German UI reason + a retry time) and re-enqueues with backoff
instead of erroring. The ``waiting`` run state surfaces in the UI as "wartet auf …".
"""

import random
from collections.abc import Callable

# Machine codes for the blocked dependency (stored in ``CaseRunDB.blocked_on``).
BLOCKED_AI_TOOLS = "ai_tools"  # OCR / anonymisation GPU node
BLOCKED_LLM = "llm"
BLOCKED_ADAPTER = "adapter"

# German UI strings (``CaseRunDB.blocked_reason``) for the "wartet auf …" banner.
BLOCKED_REASONS = {
    BLOCKED_AI_TOOLS: (
        "Wartet auf den GPU-Dienst (OCR/Anonymisierung) — er schläft oder ist ausgelastet."
    ),
    BLOCKED_LLM: "Wartet auf den KI-Dienst (LLM).",
    BLOCKED_ADAPTER: "Wartet auf die Kanzleisoftware.",
}

# Backoff schedule (seconds) by retry attempt — covers a Wake-on-LAN boot window.
_BACKOFF = [30, 60, 120, 240, 480]


def backoff_for(attempt: int) -> int:
    """Seconds to defer the next retry for the given (0-based) attempt (the cap)."""
    return _BACKOFF[min(max(attempt, 0), len(_BACKOFF) - 1)]


def backoff_with_jitter(attempt: int, *, rng: Callable[[], float] = random.random) -> float:
    """Seconds to defer the next retry — the schedule cap with *equal jitter*.

    The wait grows with ``attempt`` (30→60→120→240→480 s, covering a slow
    Wake-on-LAN boot) but is randomised within ``[cap/2, cap]`` so that many runs
    blocked at the same instant don't retry in lockstep and stampede the single
    GPU the moment it returns. ``rng`` (→ ``[0, 1)``) is injectable for
    deterministic tests.
    """
    cap = backoff_for(attempt)
    return cap / 2 + rng() * (cap / 2)


class DependencyUnavailable(Exception):
    """A *temporary* external-dependency outage — the run should WAIT + retry, not
    fail. Raised by dependency calls (OCR / anonymise / LLM / adapter) on a
    transport error (connection refused / timeout) after a wake attempt.

    Carries only *what* is down (``blocked_on`` + the German ``blocked_reason``);
    the retry backoff is owned by ``tracked_run``, which derives it from arq's
    authoritative ``job_try`` so it escalates correctly across attempts.
    """

    def __init__(self, blocked_on: str):
        self.blocked_on = blocked_on
        self.blocked_reason = BLOCKED_REASONS.get(
            blocked_on, "Wartet auf einen externen Dienst.",
        )
        super().__init__(f"{blocked_on} unavailable")
