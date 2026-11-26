"""Optional comparison of the registered domain with a reference collection.

The collection is a versioned JSON file named by REFERENCE_DOMAINS_FILE:

    {"version": "2026-11-01", "domains": ["example.com", "example.org"]}

No collection is shipped or enabled by default. Similarity is a measure of
spelling only; neither a close nor an exact match says anything about safety.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz.distance import JaroWinkler, Levenshtein

from app.services.url_inspection.parsing import InvalidUrl, parse_url

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class ReferenceCollection:
    version: str | None = None
    domains: tuple[str, ...] = ()  # normalised Unicode registered domains
    # Why the collection cannot be used: not_configured | load_error | empty_collection
    problem: str | None = "not_configured"


def _normalize_entry(entry: Any) -> str | None:
    """An entry must itself be a registered domain (not a URL or subdomain)."""
    if not isinstance(entry, str) or any(char in entry for char in "/:@?#\\"):
        return None
    try:
        parsed = parse_url(entry)
    except InvalidUrl:
        return None
    if parsed.unicode_registered_domain != parsed.unicode_hostname:
        return None
    return parsed.unicode_registered_domain


def load_collection(path: Path | None) -> ReferenceCollection:
    """Read the collection. Problems are reported, never raised."""
    if path is None:
        return ReferenceCollection()
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("file too large")
        content = json.loads(path.read_text(encoding="utf-8-sig"))
        version, entries = content["version"], content["domains"]
        if not isinstance(version, str) or not version.strip() or not isinstance(entries, list):
            raise ValueError("unexpected structure")
    except (OSError, ValueError, KeyError, TypeError) as error:
        logger.warning("Reference domain file could not be loaded (%s).", type(error).__name__)
        return ReferenceCollection(problem="load_error")

    normalized = [_normalize_entry(entry) for entry in entries]
    skipped = normalized.count(None)
    if skipped:
        logger.warning("Reference domain file: %d entries are not registered domains and were skipped.", skipped)
    domains = tuple(sorted({domain for domain in normalized if domain}))
    return ReferenceCollection(version.strip(), domains, None if domains else "empty_collection")


def _unavailable(reason: str, collection: ReferenceCollection) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "collectionVersion": collection.version,
        "collectionSize": len(collection.domains),
        "match": None,
    }


def compare(registered_domain: str | None, collection: ReferenceCollection) -> dict[str, Any]:
    """Nearest reference: highest Levenshtein similarity, then Jaro-Winkler, then name.

    Both values are RapidFuzz normalised similarities (0-1) over the whole
    registered domain, so a different suffix lowers them.
    """
    if collection.problem:
        return _unavailable(collection.problem, collection)
    if registered_domain is None:
        return _unavailable("no_registered_domain", collection)

    def scores(reference: str) -> tuple[float, float]:
        return (
            Levenshtein.normalized_similarity(registered_domain, reference),
            JaroWinkler.normalized_similarity(registered_domain, reference),
        )

    nearest = max(collection.domains, key=scores)
    levenshtein, jaro_winkler = scores(nearest)
    return {
        "status": "available",
        "reason": None,
        "collectionVersion": collection.version,
        "collectionSize": len(collection.domains),
        "match": {
            "reference": nearest,
            "exactMatch": nearest == registered_domain,
            "levenshteinSimilarity": round(levenshtein, 4),
            "jaroWinklerSimilarity": round(jaro_winkler, 4),
        },
    }
