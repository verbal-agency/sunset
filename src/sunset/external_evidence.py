"""Extraction and conservative assessment of explicitly cited external evidence."""

from __future__ import annotations

import re

from sunset.artifact_store import ArtifactStore
from sunset.evidence_providers import EvidenceProvider
from sunset.external_evidence_models import AssumptionAssessment, ExternalReference, ProviderResolution


_GITHUB_REFERENCE = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/\d+/?"
)
_RELEASE_NOTE_REFERENCE = re.compile(
    r"(?:release[- ]?notes?|changelog)\s*[:=]\s*(https?://[^\s'\"),]+)",
    re.IGNORECASE,
)
_VERSIONED_RELEASE_NOTE_REFERENCE = re.compile(
    r"(?:release[- ]?notes?|changelog)\s*[:=]\s*([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)\s+(https?://[^\s'\"),]+)",
    re.IGNORECASE,
)


def extract_external_references(values: tuple[str, ...]) -> tuple[ExternalReference, ...]:
    """Return only explicit, unambiguous source references in stable order."""

    references: list[ExternalReference] = []
    for value in values:
        for match in _GITHUB_REFERENCE.finditer(value):
            _append_once(references, ExternalReference("github", match.group(0).rstrip("/")))
        versioned_locators: set[str] = set()
        for match in _VERSIONED_RELEASE_NOTE_REFERENCE.finditer(value):
            locator = match.group(3).rstrip("/")
            versioned_locators.add(locator)
            _append_once(
                references,
                ExternalReference("release_note", locator, match.group(1), match.group(2)),
            )
        for match in _RELEASE_NOTE_REFERENCE.finditer(value):
            locator = match.group(1).rstrip("/")
            if locator not in versioned_locators:
                _append_once(references, ExternalReference("release_note", locator))
    return tuple(references)


def assess_assumption(
    references: tuple[ExternalReference, ...],
    provider: EvidenceProvider | None,
    store: ArtifactStore,
) -> AssumptionAssessment:
    """Classify external support without treating any result as removal evidence."""

    if not references:
        return AssumptionAssessment("unknown", ())
    if provider is None:
        resolutions = tuple(
            ProviderResolution(
                reference,
                "failed",
                "External evidence was not requested; assumption status remains unknown.",
                reference.locator,
                error_kind="provider_not_configured",
            )
            for reference in references
        )
        return AssumptionAssessment("unknown", resolutions)
    resolutions = tuple(provider.resolve(reference, store) for reference in references)
    outcomes = {item.outcome for item in resolutions}
    if "supports_active" in outcomes and "supports_expired" in outcomes:
        return AssumptionAssessment("unknown", resolutions)
    if outcomes == {"supports_expired"}:
        return AssumptionAssessment("expired", resolutions)
    if outcomes == {"supports_active"}:
        return AssumptionAssessment("active", resolutions)
    return AssumptionAssessment("unknown", resolutions)


def _append_once(references: list[ExternalReference], reference: ExternalReference) -> None:
    if reference not in references:
        references.append(reference)
