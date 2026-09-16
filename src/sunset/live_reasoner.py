"""A bounded live agent reasoner for the escalation loop.

Given per-case evidence, it makes ONE model call and returns a condition status in
the loop's four-value vocabulary. It is deliberately conservative: anything it
cannot parse becomes ``unknown``, which the loop treats as a reason to escalate to
empirical validation rather than to guess. Model output is a hypothesis, never
authority — the disposable-clone result still adjudicates.

The model is injected (built via ``live_model.build_chat_model``) and duck-typed:
any object with ``invoke(prompt) -> response`` where ``response`` has ``.content``
(or is a string) works, so tests run offline with a stub.
"""

from __future__ import annotations

from typing import Any, Callable

from sunset.escalation_loop_models import ConditionStatus

# Per-case evidence: case_id -> compact evidence text (e.g. marker reason + context).
EvidenceProvider = Callable[[str], str]

_SYSTEM = (
    "You assess whether the protected condition behind a disabled test or "
    "compatibility marker is still in force. You never decide to remove code. "
    "Given the evidence, classify the condition as exactly one of:\n"
    "  likely_active     - the condition that justified the marker probably still holds\n"
    "  likely_expired    - the condition has probably passed; the marker may be stale\n"
    "  unknown           - the evidence is insufficient to tell\n"
    "  contradictory     - the evidence points both ways\n"
    "Be conservative: prefer unknown over guessing. Reply with a final line "
    "'STATUS: <value>'."
)

_VALID: frozenset[str] = frozenset({"likely_active", "likely_expired", "unknown", "contradictory"})


def build_prompt(evidence: str) -> str:
    return f"{_SYSTEM}\n\nEVIDENCE:\n{evidence}\n\nClassify now."


def parse_status(text: str) -> ConditionStatus:
    """Extract the status token; unparseable or absent -> 'unknown' (fail-safe)."""

    lowered = text.lower()
    # Prefer an explicit 'status:' line if present.
    for line in reversed(lowered.splitlines()):
        if "status:" in line:
            tail = line.split("status:", 1)[1]
            for value in _VALID:
                if value in tail:
                    return value  # type: ignore[return-value]
    # Otherwise, accept a unique unambiguous mention.
    hits = [value for value in _VALID if value in lowered]
    if len(hits) == 1:
        return hits[0]  # type: ignore[return-value]
    return "unknown"


def _content(response: Any) -> str:
    if isinstance(response, str):
        return response
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some chat models return content parts
        return " ".join(str(part) for part in content)
    return str(content)


class LiveAgentReasoner:
    """One bounded model call per case, returning a condition status."""

    def __init__(self, model: Any, evidence: EvidenceProvider, *, max_evidence_chars: int = 4000) -> None:
        self._model = model
        self._evidence = evidence
        self._max_evidence_chars = max_evidence_chars

    def __call__(self, case_id: str) -> ConditionStatus:
        evidence = (self._evidence(case_id) or "")[: self._max_evidence_chars]
        try:
            response = self._model.invoke(build_prompt(evidence))
        except Exception:  # noqa: BLE001 - a model/transport failure must not crash the loop
            return "unknown"
        return parse_status(_content(response))


def recorded_evidence(mapping: dict[str, str]) -> EvidenceProvider:
    def provide(case_id: str) -> str:
        return mapping.get(case_id, "")

    return provide


__all__ = [
    "EvidenceProvider",
    "LiveAgentReasoner",
    "build_prompt",
    "parse_status",
    "recorded_evidence",
]
