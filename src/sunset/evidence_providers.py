"""Replaceable, artifact-backed evidence providers for external assumptions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sunset.artifact_store import ArtifactStore
from sunset.external_evidence_models import ExternalReference, ProviderResolution


class EvidenceProvider(Protocol):
    name: str

    def resolve(self, reference: ExternalReference, store: ArtifactStore) -> ProviderResolution:
        """Resolve one explicit reference without turning it into an authority."""


class RecordedEvidenceProvider:
    """A deterministic provider backed by a checked-in JSON fixture file."""

    name = "recorded"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser().resolve()
        try:
            value = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._records: dict[tuple[str, str], dict[str, object]] = {}
            self._load_error = str(exc)
        else:
            self._load_error = None
            self._records = {
                (str(item["provider"]), str(item["locator"])): item
                for item in value.get("responses", [])
            }

    def resolve(self, reference: ExternalReference, store: ArtifactStore) -> ProviderResolution:
        if self._load_error is not None:
            return ProviderResolution(
                reference, "failed", "Recorded evidence fixture could not be loaded.",
                str(self.fixture_path), error_kind="recorded_fixture_unavailable",
            )
        record = self._records.get((reference.provider, reference.locator))
        if record is None:
            return ProviderResolution(
                reference, "missing", "No recorded response exists for this explicit reference.",
                reference.locator,
            )
        outcome = str(record.get("outcome", "failed"))
        if outcome not in {"supports_active", "supports_expired"}:
            return ProviderResolution(
                reference,
                "missing" if outcome == "missing" else "failed",
                str(record.get("summary", "Recorded provider response was unavailable.")),
                reference.locator,
                error_kind=str(record.get("error_kind")) if record.get("error_kind") else None,
            )
        raw = _canonical_json(record)
        artifact = store.put(
            raw,
            media_type="application/json",
            source_kind=f"recorded_{reference.provider}_response",
            source_locator=reference.locator,
        )
        return ProviderResolution(
            reference,
            outcome,
            str(record.get("summary", "Recorded evidence supports this assumption status.")),
            reference.locator,
            artifact=artifact,
        )


class LiveGitHubProvider:
    """Optional GitHub JSON fetcher; it is never selected by default."""

    name = "live_github"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def resolve(self, reference: ExternalReference, store: ArtifactStore) -> ProviderResolution:
        if not self.token:
            return ProviderResolution(
                reference, "failed", "Live GitHub evidence requires GITHUB_TOKEN.", reference.locator,
                error_kind="credentials_unavailable",
            )
        if reference.provider != "github":
            return ProviderResolution(reference, "failed", "GitHub provider cannot resolve this reference.", reference.locator, error_kind="unsupported_reference")
        api_url = _github_api_url(reference.locator)
        if api_url is None:
            return ProviderResolution(reference, "failed", "GitHub reference is not a supported issue or pull-request URL.", reference.locator, error_kind="unsupported_reference")
        try:
            request = Request(api_url, headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}"})
            with urlopen(request, timeout=10) as response:  # noqa: S310 - deliberate opt-in boundary
                raw = response.read()
        except (HTTPError, URLError, OSError) as exc:
            return ProviderResolution(reference, "failed", "Live GitHub lookup failed; no expiry conclusion was made.", reference.locator, error_kind=type(exc).__name__.lower())
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return ProviderResolution(reference, "failed", "Live GitHub returned malformed JSON.", reference.locator, error_kind="malformed_response")
        state = str(payload.get("state", ""))
        outcome = "supports_active" if state == "open" else "supports_expired" if state == "closed" else "failed"
        if outcome == "failed":
            return ProviderResolution(reference, "failed", "Live GitHub response did not contain a usable state.", reference.locator, error_kind="malformed_response")
        artifact = store.put(raw, media_type="application/json", source_kind="live_github_response", source_locator=reference.locator)
        return ProviderResolution(reference, outcome, f"Live GitHub reports the reference as {state}.", reference.locator, artifact=artifact)


class UnavailableLiveReleaseNoteProvider:
    """An explicit live boundary pending a configured release-note adapter."""

    name = "live_release_note"

    def resolve(self, reference: ExternalReference, store: ArtifactStore) -> ProviderResolution:
        return ProviderResolution(
            reference, "failed", "No live release-note provider is configured.", reference.locator,
            error_kind="provider_unavailable",
        )


def _github_api_url(locator: str) -> str | None:
    prefix = "https://github.com/"
    if not locator.startswith(prefix):
        return None
    parts = locator[len(prefix):].rstrip("/").split("/")
    if len(parts) != 4 or parts[2] not in {"issues", "pull"} or not parts[3].isdigit():
        return None
    return f"https://api.github.com/repos/{parts[0]}/{parts[1]}/issues/{parts[3]}"


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
