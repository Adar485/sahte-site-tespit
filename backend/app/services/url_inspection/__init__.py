"""URL-only inspection: facts about an address, derived from its text alone.

Nothing in this package visits the address or performs any network request
(no HTTP, DNS, WHOIS, TLS or redirect lookups). It produces no verdict,
probability or risk score; that is the job of the future classifier.
"""

from app.services.url_inspection.inspector import FEATURE_SCHEMA_VERSION, UrlInspection, inspect_url
from app.services.url_inspection.parsing import MAX_URL_LENGTH, InvalidUrl, ParsedUrl, parse_url

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "MAX_URL_LENGTH",
    "InvalidUrl",
    "ParsedUrl",
    "UrlInspection",
    "inspect_url",
    "parse_url",
]
