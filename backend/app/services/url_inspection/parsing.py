"""Parsing and normalisation of a submitted address.

parse_url() is the single normalisation path: the API uses it to accept or
reject a submission and the inspector uses it to measure the address.

Rules (frontend/src/lib/url.ts mirrors them; shared cases: tests/url_validation_cases.json):
- Surrounding whitespace is removed; inner whitespace and control characters are rejected.
- Input without "scheme://" gets "https://" (recorded as scheme_assumed).
- Only http and https are accepted.
- A backslash before the query or fragment is rejected: browsers read it as "/", other
  parsers do not, so the address is ambiguous.
- User information ("@" in the authority), even empty or a user name only, is rejected.
- The hostname is percent-decoded, UTS #46 mapped (which lowercases it), stripped of
  one trailing dot and converted to its ASCII (punycode) form with IDNA 2008.
- Path, query and fragment are kept exactly as written (case, encoding, dot segments).
- The default port (80/443) is left out of the normalised URL.
"""

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import idna
import tldextract

MAX_URL_LENGTH = 2048
DEFAULT_PORTS = {"http": 80, "https": 443}

# suffix_list_urls=() forbids downloading: the Public Suffix List snapshot bundled with
# the installed tldextract version is used. cache_dir=None avoids reading a stale cache
# or writing one. The list is therefore as new as the installed package.
# Private suffixes (github.io and the like) are not treated as public suffixes.
_extract_suffix = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=False)

# re.ASCII: otherwise IGNORECASE lets "İ" match "i" and "ſ" match "s".
_EXPLICIT_SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*)://", re.IGNORECASE | re.ASCII)
# Same list as frontend/src/lib/url.ts.
_NON_WEB_SCHEME = re.compile(
    r"^(javascript|data|file|mailto|tel|sms|ftp|ftps|about|blob|vbscript|chrome|ws|wss|ssh|smb):", re.IGNORECASE | re.ASCII
)
_ASCII_LABEL = re.compile(r"^[a-z0-9_-]+$")
_FORBIDDEN_IN_HOST = re.compile(r"[\x00-\x20\x7f#/:<>?@\[\\\]^|%]")


class InvalidUrl(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParsedUrl:
    submitted: str  # trimmed input, otherwise untouched
    normalized: str
    scheme: str
    scheme_assumed: bool
    host_type: str  # "domain" | "ipv4" | "ipv6"
    hostname: str  # ASCII form, IPv6 without brackets
    unicode_hostname: str
    non_standard_ip_notation: bool
    port: int | None  # only when written in the address
    subdomain: str | None  # None: unknown or not applicable; "": no subdomain
    registered_domain: str | None
    unicode_registered_domain: str | None
    public_suffix: str | None
    suffix_known: bool | None  # None for IP addresses
    path: str
    query: str
    fragment: str

    @property
    def effective_port(self) -> int:
        return self.port if self.port is not None else DEFAULT_PORTS[self.scheme]


def _invalid_host() -> InvalidUrl:
    return InvalidUrl("invalid_host", "Alan adı eksik ya da hatalı görünüyor.")


def _malformed() -> InvalidUrl:
    return InvalidUrl("malformed", "Bu bir web adresine benzemiyor.")


def _unsupported_scheme() -> InvalidUrl:
    return InvalidUrl("unsupported_scheme", "Yalnızca http:// veya https:// ile başlayan web adresleri incelenebilir.")


def _parse_port(text: str) -> int | None:
    if not text:
        return None
    if not re.fullmatch(r"[0-9]{1,5}", text) or not 1 <= int(text) <= 65535:
        raise InvalidUrl("invalid_port", "Port numarası geçersiz. 1 ile 65535 arasında bir sayı olmalıdır.")
    return int(text)


def _split_host_port(host_port: str) -> tuple[str, bool, int | None]:
    """Returns (host, was_bracketed, port)."""
    if host_port.startswith("["):
        host, closing, rest = host_port[1:].partition("]")
        if not closing or (rest and not rest.startswith(":")):
            raise _malformed()
        return host, True, _parse_port(rest[1:])
    if host_port.count(":") > 1:
        raise _invalid_host()  # IPv6 addresses must be written in brackets
    host, _, port = host_port.partition(":")
    return host, False, _parse_port(port)


def _ipv4_number(text: str) -> int | None:
    """One part of an IPv4 address as browsers read it: decimal, 0-octal or 0x-hex."""
    if re.fullmatch(r"0x[0-9a-f]*", text):
        return int(text[2:] or "0", 16)
    if re.fullmatch(r"0[0-7]+", text):
        return int(text, 8)
    if re.fullmatch(r"0|[1-9][0-9]*", text):
        return int(text)
    return None


def _parse_ipv4(labels: list[str]) -> ipaddress.IPv4Address:
    numbers = [_ipv4_number(label) for label in labels]
    if len(numbers) > 4 or any(number is None for number in numbers):
        raise _invalid_host()
    *head, last = numbers
    if any(number > 255 for number in head) or last >= 256 ** (4 - len(head)):
        raise _invalid_host()
    value = last + sum(number * 256 ** (3 - index) for index, number in enumerate(head))
    return ipaddress.IPv4Address(value)


def _encode_labels(labels: list[str]) -> tuple[list[str], list[str]]:
    """Return (ASCII labels, Unicode labels), validating each one."""
    ascii_labels: list[str] = []
    unicode_labels: list[str] = []
    for label in labels:
        try:
            if label.startswith("xn--"):
                ascii_label, unicode_label = label, idna.ulabel(label)
                # Only the canonical punycode spelling of a name is accepted.
                if idna.alabel(unicode_label).decode("ascii") != label:
                    raise _invalid_host()
            elif label.isascii():
                if not _ASCII_LABEL.match(label):
                    raise _invalid_host()
                ascii_label = unicode_label = label
            else:
                ascii_label, unicode_label = idna.alabel(label).decode("ascii"), label
        except (UnicodeError, IndexError) as error:  # idna.IDNAError is a UnicodeError
            raise _invalid_host() from error
        if not 1 <= len(ascii_label) <= 63:
            raise _invalid_host()
        ascii_labels.append(ascii_label)
        unicode_labels.append(unicode_label)
    return ascii_labels, unicode_labels


@dataclass(frozen=True)
class _Host:
    host_type: str
    ascii: str
    unicode: str
    non_standard_ip: bool = False
    subdomain: str | None = None
    registered_domain: str | None = None
    unicode_registered_domain: str | None = None
    public_suffix: str | None = None
    suffix_known: bool | None = None


def _parse_host(raw_host: str, bracketed: bool) -> _Host:
    if bracketed:
        try:
            address = ipaddress.IPv6Address(raw_host)
        except ValueError as error:
            raise _invalid_host() from error
        if "%" in raw_host:  # zone identifiers have no meaning outside one machine
            raise _invalid_host()
        return _Host("ipv6", address.compressed, address.compressed)

    try:
        decoded = unquote(raw_host, errors="strict")
        mapped = idna.uts46_remap(decoded, std3_rules=False, transitional=False)
    except (UnicodeError, IndexError) as error:
        raise _invalid_host() from error
    mapped = mapped.removesuffix(".")
    if not mapped or _FORBIDDEN_IN_HOST.search(mapped):
        raise _invalid_host()
    labels = mapped.split(".")
    if "" in labels:
        raise _invalid_host()

    if re.fullmatch(r"[0-9]+|0x[0-9a-f]*", labels[-1]):
        address = _parse_ipv4(labels)
        written = raw_host.removesuffix(".")
        return _Host("ipv4", str(address), str(address), non_standard_ip=written != str(address))

    ascii_labels, unicode_labels = _encode_labels(labels)
    ascii_host = ".".join(ascii_labels)
    top = unicode_labels[-1]
    if (
        len(labels) < 2
        or len(ascii_host) > 253
        or ascii_host.startswith("-")
        or not (ascii_labels[-1].startswith("xn--") or (len(top) >= 2 and top.isalpha()))
    ):
        raise _invalid_host()
    unicode_host = ".".join(unicode_labels)

    # Only the number of suffix labels is taken from tldextract, so the same split
    # applies to the ASCII and the Unicode form.
    suffix = _extract_suffix(unicode_host).suffix
    if not suffix:
        return _Host("domain", ascii_host, unicode_host, suffix_known=False)
    size = len(suffix.split("."))
    public_suffix = ".".join(ascii_labels[-size:])
    if len(labels) <= size:  # the host is itself a public suffix, e.g. "co.uk"
        return _Host("domain", ascii_host, unicode_host, public_suffix=public_suffix, suffix_known=True)
    return _Host(
        "domain",
        ascii_host,
        unicode_host,
        subdomain=".".join(ascii_labels[: -(size + 1)]),
        registered_domain=".".join(ascii_labels[-(size + 1) :]),
        unicode_registered_domain=".".join(unicode_labels[-(size + 1) :]),
        public_suffix=public_suffix,
        suffix_known=True,
    )


def parse_url(raw: str) -> ParsedUrl:
    value = raw.strip()
    if not value:
        raise InvalidUrl("empty", "İncelemek istediğiniz web adresini yazın.")
    if len(value) > MAX_URL_LENGTH:
        raise InvalidUrl("too_long", "Bu adres çok uzun. En fazla 2048 karakterlik adresler incelenebilir.")
    if re.search(r"\s", value):
        raise InvalidUrl("whitespace", "Adres boşluk içeremez.")
    if any(unicodedata.category(char) in ("Cc", "Cs") for char in value):
        raise _malformed()

    explicit = _EXPLICIT_SCHEME.match(value)
    if explicit:
        if explicit.group(1).lower() not in DEFAULT_PORTS:
            raise _unsupported_scheme()
    elif _NON_WEB_SCHEME.match(value):
        raise _unsupported_scheme()
    if "\\" in re.split(r"[?#]", value, maxsplit=1)[0]:
        raise InvalidUrl("backslash", "Adreste ters eğik çizgi (\\) kullanılamaz; “/” kullanın.")
    if not explicit and re.match(r"https?:", value, re.IGNORECASE | re.ASCII):
        raise _malformed()  # "https:host" or "https:/host"
    candidate = value if explicit else f"https://{value.removeprefix('//')}"

    # Checked on the raw authority, before any other host or port rule, so such input is
    # always refused for this reason. The message never repeats any part of the input.
    if "@" in re.split(r"[/?#]", candidate.partition("://")[2], maxsplit=1)[0]:
        raise InvalidUrl(
            "credentials_not_allowed",
            "Kullanıcı adı veya parola içeren adresler kabul edilmiyor. “@” öncesindeki giriş bilgilerini kaldırın.",
        )

    try:
        parts = urlsplit(candidate)
    except ValueError as error:
        raise _malformed() from error

    if not parts.netloc:
        raise _malformed()
    raw_host, bracketed, port = _split_host_port(parts.netloc)
    host = _parse_host(raw_host, bracketed)

    authority = f"[{host.ascii}]" if host.host_type == "ipv6" else host.ascii
    if port is not None and port != DEFAULT_PORTS[parts.scheme]:
        authority += f":{port}"
    normalized = f"{parts.scheme}://{authority}{parts.path or '/'}"
    if parts.query:
        normalized += f"?{parts.query}"
    if parts.fragment:
        normalized += f"#{parts.fragment}"

    return ParsedUrl(
        submitted=value,
        normalized=normalized,
        scheme=parts.scheme,
        scheme_assumed=not explicit,
        host_type=host.host_type,
        hostname=host.ascii,
        unicode_hostname=host.unicode,
        non_standard_ip_notation=host.non_standard_ip,
        port=port,
        subdomain=host.subdomain,
        registered_domain=host.registered_domain,
        unicode_registered_domain=host.unicode_registered_domain,
        public_suffix=host.public_suffix,
        suffix_known=host.suffix_known,
        path=parts.path,
        query=parts.query,
        fragment=parts.fragment,
    )
