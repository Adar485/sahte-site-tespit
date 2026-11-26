"""Script mixing and confusable characters in a hostname.

Script and confusable data come from the confusable_homoglyphs package, which
ships the Unicode Consortium's Scripts and UTS #39 confusables data.

This is NOT complete homograph detection:
- only non-ASCII characters that look like an ASCII letter or digit are reported
  (ASCII tricks such as "0"/"o", "1"/"l" or "rn"/"m" are not);
- a label written entirely in one non-Latin script is reported only when every
  one of its letters has an ASCII look-alike, so ordinary words in that script
  are not flagged;
- font-dependent similarity and look-alikes between two non-Latin scripts are
  not covered;
- the data is as new as the installed package.
"""

from typing import Any

from confusable_homoglyphs import categories, confusables

# Combinations UTS #39 "Highly Restrictive" accepts: normal Japanese, Chinese and Korean writing.
_EXPECTED_MIXES = (
    {"LATIN", "HAN", "HIRAGANA", "KATAKANA"},
    {"LATIN", "HAN", "BOPOMOFO"},
    {"LATIN", "HAN", "HANGUL"},
)
_NEUTRAL_SCRIPTS = {"COMMON", "INHERITED", "UNKNOWN"}


def _script(char: str) -> str:
    return categories.alias(char).upper()


def _ascii_lookalike(char: str) -> str | None:
    matches = sorted(
        entry["c"]
        for entry in confusables.confusables_data.get(char, [])
        if len(entry["c"]) == 1 and entry["c"].isascii() and entry["c"].isalnum()
    )
    if not matches:
        return None
    lowercase = [match for match in matches if match.islower()]
    return (lowercase or matches)[0]


def check_hostname(unicode_hostname: str) -> dict[str, Any]:
    """Inspect a lowercased Unicode hostname label by label."""
    mixed: list[dict[str, Any]] = []
    found: list[dict[str, str]] = []
    for label in unicode_hostname.split("."):
        if label.isascii():
            continue
        scripts = {_script(char) for char in label} - _NEUTRAL_SCRIPTS
        is_mixed = len(scripts) > 1 and not any(scripts <= expected for expected in _EXPECTED_MIXES)
        if is_mixed:
            mixed.append({"label": label, "scripts": sorted(scripts)})

        candidates = [
            (char, lookalike)
            for char in dict.fromkeys(label)
            if not char.isascii() and (lookalike := _ascii_lookalike(char)) is not None
        ]
        if not is_mixed and scripts != {"LATIN"}:
            whole_label = all(_ascii_lookalike(char) for char in label if char.isalpha())
            if not whole_label:
                continue
        found.extend(
            {
                "label": label,
                "character": char,
                "codePoint": f"U+{ord(char):04X}",
                "script": _script(char),
                "looksLike": lookalike,
            }
            for char, lookalike in candidates
        )
    return {"mixedScriptLabels": mixed, "confusableCharacters": found}
