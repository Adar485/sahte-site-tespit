"""Features and findings for one address.

Feature definitions (schema 1.0); see backend/README.md for the same table:

    normalizedUrlLength     characters of the normalised URL
    hostnameLength          characters of the ASCII hostname (IPv6 without brackets)
    registeredDomainLength  characters of the ASCII registered domain, or None
    subdomainCount          labels left of the registered domain, or None if unknown
    hostnameDigitRatio      ASCII digits / all characters of the Unicode hostname
    hostnameHyphenCount     "-" characters in the Unicode hostname
    pathDepth               non-empty "/" segments of the path as written
    queryParameterCount     non-empty "&" pieces of the query
    hasExplicitPort         a port is written in the address (even the default one)
    isIpAddress             the host is an IPv4 or IPv6 address
    usesHttps               the scheme is https (possibly assumed, see schemeAssumed)
    hasPercentEncoding      "%XX" appears anywhere in the submitted address
    hasIdn                  a hostname label is non-ASCII or punycode

None of these is, by itself, evidence of safety or of phishing.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.url_inspection.parsing import DEFAULT_PORTS, ParsedUrl, parse_url
from app.services.url_inspection.references import compare, load_collection
from app.services.url_inspection.unicode_checks import check_hostname

FEATURE_SCHEMA_VERSION = "1.0"
MAX_PARAMETER_NAMES = 50
MAX_NAME_LENGTH = 100

_SCRIPT_NAMES = {
    "LATIN": "Latin",
    "CYRILLIC": "Kiril",
    "GREEK": "Yunan",
    "ARMENIAN": "Ermeni",
    "HEBREW": "İbrani",
    "ARABIC": "Arap",
    "HAN": "Çin (Han)",
    "HIRAGANA": "Hiragana",
    "KATAKANA": "Katakana",
    "HANGUL": "Hangul",
    "THAI": "Tay",
    "GEORGIAN": "Gürcü",
    "DEVANAGARI": "Devanagari",
}


@dataclass(frozen=True)
class UrlInspection:
    summary: str
    findings: list[dict[str, str]]
    data: dict[str, Any]  # frontend UrlInspectionData


def _query_structure(query: str) -> dict[str, Any]:
    """Names and counts only, as written. Values are not repeated here."""
    pairs = [piece.partition("=") for piece in query.split("&") if piece]
    names = [name for name, _, _ in pairs]
    unique = list(dict.fromkeys(names))
    seen: set[str] = set()
    repeated: dict[str, None] = {}
    for name in names:
        if name in seen:
            repeated[name] = None
        seen.add(name)
    return {
        "parameterCount": len(pairs),
        "names": [name[:MAX_NAME_LENGTH] for name in unique[:MAX_PARAMETER_NAMES]],
        "repeatedNames": [name[:MAX_NAME_LENGTH] for name in list(repeated)[:MAX_PARAMETER_NAMES]],
        "emptyValueCount": sum(1 for _, _, value in pairs if not value),
    }


def _features(parsed: ParsedUrl, query: dict[str, Any]) -> dict[str, Any]:
    host = parsed.unicode_hostname
    is_ip = parsed.host_type != "domain"
    return {
        "normalizedUrlLength": len(parsed.normalized),
        "hostnameLength": len(parsed.hostname),
        "registeredDomainLength": len(parsed.registered_domain) if parsed.registered_domain else None,
        "subdomainCount": None if parsed.subdomain is None else len(parsed.subdomain.split(".")) if parsed.subdomain else 0,
        "hostnameDigitRatio": round(sum(char in "0123456789" for char in host) / len(host), 4),
        "hostnameHyphenCount": host.count("-"),
        "pathDepth": sum(1 for segment in parsed.path.split("/") if segment),
        "queryParameterCount": query["parameterCount"],
        "hasExplicitPort": parsed.port is not None,
        "isIpAddress": is_ip,
        "usesHttps": parsed.scheme == "https",
        "hasPercentEncoding": re.search(r"%[0-9A-Fa-f]{2}", parsed.submitted) is not None,
        "hasIdn": any(label.startswith("xn--") for label in parsed.hostname.split(".")),
    }


def _script_name(script: str) -> str:
    return _SCRIPT_NAMES.get(script, script.title())


def _findings(
    parsed: ParsedUrl, features: dict[str, Any], unicode: dict[str, Any], reference: dict[str, Any]
) -> list[dict[str, str]]:
    """Observed facts only. All are informational: no single one implies intent."""
    found: list[dict[str, str]] = []

    def add(key: str, title: str, description: str) -> None:
        found.append({"id": f"url-{key}", "severity": "info", "title": title, "description": description})

    if parsed.scheme_assumed:
        add("scheme-assumed", "Şema belirtilmemiş", "Adres şema belirtilmeden girildi; inceleme için https:// varsayıldı.")
    elif parsed.scheme == "http":
        add("http", "Şifresiz bağlantı şeması", "Adres HTTPS yerine HTTP kullanıyor.")
    if features["isIpAddress"]:
        add("ip-host", "IP adresi kullanımı", "Adres, alan adı yerine IP adresi kullanıyor.")
    if parsed.non_standard_ip_notation:
        add("ip-notation", "Farklı IP yazımı", f"IP adresi alışılmış biçimden farklı yazılmış; karşılığı {parsed.hostname}.")
    if parsed.port is not None and parsed.port != DEFAULT_PORTS[parsed.scheme]:
        add("port", "Varsayılan olmayan port", f"Adres, bu şema için varsayılan olmayan {parsed.port} portunu belirtiyor.")
    if parsed.suffix_known is False:
        add(
            "unknown-suffix",
            "Tanınmayan uzantı",
            "Uzantı, kullanılan Public Suffix List sürümünde yok; kayıtlı alan adı belirlenemedi.",
        )
    if parsed.registered_domain and parsed.subdomain and parsed.subdomain != "www":
        add(
            "subdomain",
            "Alt alan adı",
            f"Kayıtlı alan adı {parsed.registered_domain}; önündeki “{parsed.subdomain}” bölümü yalnızca alt alan adıdır.",
        )
    if features["hasIdn"]:
        add(
            "idn",
            "Uluslararası alan adı (IDN)",
            f"Görünen ad {parsed.unicode_hostname}, ASCII karşılığı {parsed.hostname}. IDN kullanımı tek başına sorun göstergesi değildir.",
        )
    for index, item in enumerate(unicode["mixedScriptLabels"]):
        scripts = ", ".join(_script_name(script) for script in item["scripts"])
        add(
            f"mixed-script-{index}",
            "Karışık yazı sistemi",
            f"Alan adında birden fazla yazı sistemi kullanılıyor: “{item['label']}” ({scripts}).",
        )
    if unicode["confusableCharacters"]:
        listed = "; ".join(
            f"“{item['character']}” ({item['codePoint']}, {_script_name(item['script'])}) “{item['looksLike']}” gibi görünebilir"
            for item in unicode["confusableCharacters"][:5]
        )
        add("confusable", "Karıştırılabilecek karakterler", f"Alan adında başka karakterlere benzeyen karakterler var: {listed}.")
    if features["hasPercentEncoding"]:
        add("percent-encoding", "Yüzde kodlaması", "Adreste yüzde kodlamalı (%XX) karakter dizileri bulunuyor.")
    if reference["match"] and reference["match"]["exactMatch"]:
        add(
            "reference-exact",
            "Referans listesiyle aynı alan adı",
            f"Kayıtlı alan adı referans listesindeki {reference['match']['reference']} ile aynı. Bu bir güvenlik garantisi değildir.",
        )
    return found


def inspect_url(url: str, reference_file: Path | None = None) -> UrlInspection:
    """Inspect an address from its text alone. Raises InvalidUrl for invalid input."""
    parsed = parse_url(url)
    query = _query_structure(parsed.query)
    features = _features(parsed, query)
    unicode = check_hostname(parsed.unicode_hostname) if parsed.host_type == "domain" else {
        "mixedScriptLabels": [],
        "confusableCharacters": [],
    }
    reference = compare(parsed.unicode_registered_domain, load_collection(reference_file))
    findings = _findings(parsed, features, unicode, reference)

    data = {
        "featureSchemaVersion": FEATURE_SCHEMA_VERSION,
        "address": {
            "normalizedUrl": parsed.normalized,
            "scheme": parsed.scheme,
            "schemeAssumed": parsed.scheme_assumed,
            "hostType": parsed.host_type,
            "hostname": parsed.hostname,
            "unicodeHostname": parsed.unicode_hostname,
            "port": parsed.port,
            "effectivePort": parsed.effective_port,
            "subdomain": parsed.subdomain,
            "registeredDomain": parsed.registered_domain,
            "publicSuffix": parsed.public_suffix,
            "suffixKnown": parsed.suffix_known,
            "path": parsed.path or "/",
            "query": query,
            "hasFragment": bool(parsed.fragment),
        },
        "features": features,
        "unicode": unicode,
        "reference": reference,
    }
    summary = (
        f"Yalnızca adres metni incelendi; {len(findings)} gözlem kaydedildi."
        if findings
        else "Yalnızca adres metni incelendi; ek bir gözlem yok."
    )
    return UrlInspection(summary=summary, findings=findings, data=data)
