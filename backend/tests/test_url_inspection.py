import json
import socket
from pathlib import Path

import pytest

from app.services.url_inspection import InvalidUrl, inspect_url, parse_url

FIXTURE = Path(__file__).parent / "fixtures" / "reference_domains.example.json"
# Also run against the frontend validator (frontend/tests/url.test.mjs).
CASES = json.loads((Path(__file__).parents[2] / "tests" / "url_validation_cases.json").read_text(encoding="utf-8"))


def data(url, reference_file=None):
    return inspect_url(url, reference_file).data


def finding_ids(url, reference_file=None):
    return {finding["id"] for finding in inspect_url(url, reference_file).findings}


def test_ordinary_https_address():
    result = data("https://www.example.com/giris")
    address, features = result["address"], result["features"]
    assert address["scheme"] == "https" and not address["schemeAssumed"]
    assert address["hostname"] == "www.example.com"
    assert (address["subdomain"], address["registeredDomain"], address["publicSuffix"]) == ("www", "example.com", "com")
    assert address["port"] is None and address["effectivePort"] == 443
    assert features == {
        "normalizedUrlLength": len("https://www.example.com/giris"),
        "hostnameLength": 15,
        "registeredDomainLength": 11,
        "subdomainCount": 1,
        "hostnameDigitRatio": 0,
        "hostnameHyphenCount": 0,
        "pathDepth": 1,
        "queryParameterCount": 0,
        "hasExplicitPort": False,
        "isIpAddress": False,
        "usesHttps": True,
        "hasPercentEncoding": False,
        "hasIdn": False,
    }
    assert inspect_url("https://www.example.com/giris").findings == []


def test_scheme_is_assumed_and_submitted_value_is_kept():
    parsed = parse_url("  Example.COM/Yol  ")
    assert parsed.submitted == "Example.COM/Yol"
    assert parsed.normalized == "https://example.com/Yol"
    assert parsed.scheme_assumed
    assert "url-scheme-assumed" in finding_ids("example.com")
    assert parse_url("//example.com").normalized == "https://example.com/"
    assert parse_url("example.com:8443/a").port == 8443


def test_misleading_subdomain():
    result = data("https://example.com.login.example.net/")
    assert result["address"]["registeredDomain"] == "example.net"
    assert result["address"]["subdomain"] == "example.com.login"
    assert result["features"]["subdomainCount"] == 3
    assert "url-subdomain" in finding_ids("https://example.com.login.example.net/")


@pytest.mark.parametrize(
    ("host", "registered", "suffix", "subdomain"),
    [
        ("shop.example.co.uk", "example.co.uk", "co.uk", "shop"),
        ("a.b.example.com.tr", "example.com.tr", "com.tr", "a.b"),
        ("co.uk", None, "co.uk", None),
    ],
)
def test_multi_part_public_suffixes(host, registered, suffix, subdomain):
    address = data(f"https://{host}/")["address"]
    assert (address["registeredDomain"], address["publicSuffix"], address["subdomain"]) == (registered, suffix, subdomain)


def test_unknown_suffix_is_explicit():
    result = data("https://login.example.test/")
    address = result["address"]
    assert address["suffixKnown"] is False
    assert address["registeredDomain"] is address["publicSuffix"] is address["subdomain"] is None
    assert result["features"]["subdomainCount"] is None
    assert result["features"]["registeredDomainLength"] is None


@pytest.mark.parametrize(
    ("url", "host_type", "hostname", "normalized"),
    [
        ("http://192.0.2.10/a", "ipv4", "192.0.2.10", "http://192.0.2.10/a"),
        ("http://[2001:DB8:0:0::1]:8080/", "ipv6", "2001:db8::1", "http://[2001:db8::1]:8080/"),
        ("[2001:db8::1]", "ipv6", "2001:db8::1", "https://[2001:db8::1]/"),
        ("http://3221225994/", "ipv4", "192.0.2.10", "http://192.0.2.10/"),
        ("http://0xC0.0.2.012/", "ipv4", "192.0.2.10", "http://192.0.2.10/"),
    ],
)
def test_ip_addresses(url, host_type, hostname, normalized):
    result = data(url)
    address = result["address"]
    assert (address["hostType"], address["hostname"], address["normalizedUrl"]) == (host_type, hostname, normalized)
    assert address["registeredDomain"] is address["publicSuffix"] is address["suffixKnown"] is None
    assert result["features"]["isIpAddress"] is True
    assert "url-ip-host" in finding_ids(url)


def test_non_standard_ip_notation_is_reported():
    assert "url-ip-notation" in finding_ids("http://3221225994/")
    assert "url-ip-notation" not in finding_ids("http://192.0.2.10/")


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("https://example.com/a b", "whitespace"),
        ("https://example.com/\x00", "malformed"),
        ("https://example.com/" + "a" * 2048, "too_long"),
        ("ftp://example.com", "unsupported_scheme"),
        ("custom://example.com", "unsupported_scheme"),
        ("javascript:alert(1)", "unsupported_scheme"),
        ("mailto:someone@example.com", "unsupported_scheme"),
        ("https://example.com:0/", "invalid_port"),
        ("https://example.com:65536/", "invalid_port"),
        ("https://example.com:abc/", "invalid_port"),
        ("https:///path", "malformed"),
        ("https://[2001:db8::1/", "malformed"),
        ("https://[not-an-address]/", "invalid_host"),
        ("https://[fe80::1%25eth0]/", "invalid_host"),
        ("https://2001:db8::1/", "invalid_host"),
        ("https://localhost/", "invalid_host"),
        ("https://exa..mple.com/", "invalid_host"),
        ("https://-example.com/", "invalid_host"),
        ("https://256.1.1.1/", "invalid_host"),
        ("https://exa%2Fmple.com/", "invalid_host"),
        ("https://" + "a" * 64 + ".com/", "invalid_host"),
        ("https://xn--zz.com/", "invalid_host"),
        ("https://xn--a.com/", "invalid_host"),
        ("https://a☃-.com/", "invalid_host"),
    ],
)
def test_rejected_input(url, code):
    with pytest.raises(InvalidUrl) as error:
        parse_url(url)
    assert error.value.code == code


def test_valid_idn_has_both_representations():
    for url in ("https://bücher.example.com/", "https://xn--bcher-kva.example.com/"):
        result = data(url)
        assert result["address"]["hostname"] == "xn--bcher-kva.example.com"
        assert result["address"]["unicodeHostname"] == "bücher.example.com"
        assert result["features"]["hasIdn"] is True
        # Hyphens added by punycode are not counted.
        assert result["features"]["hostnameHyphenCount"] == 0
        # IDN alone is informational, not a confusable finding.
        assert finding_ids(url) >= {"url-idn"}
        assert "url-confusable" not in finding_ids(url)


def test_idn_public_suffix():
    address = data("https://пример.рф/")["address"]
    assert address["registeredDomain"] == "xn--e1afmkfd.xn--p1ai"
    assert address["publicSuffix"] == "xn--p1ai"


def test_mixed_script_and_confusable_characters():
    url = "https://exаmple.com/"  # Cyrillic а inside Latin letters
    unicode = data(url)["unicode"]
    assert unicode["mixedScriptLabels"] == [{"label": "exаmple", "scripts": ["CYRILLIC", "LATIN"]}]
    assert unicode["confusableCharacters"][0]["codePoint"] == "U+0430"
    assert unicode["confusableCharacters"][0]["looksLike"] == "a"
    assert finding_ids(url) >= {"url-idn", "url-mixed-script-0", "url-confusable"}
    assert any("birden fazla yazı sistemi" in finding["description"] for finding in inspect_url(url).findings)


def test_whole_script_confusable_but_not_ordinary_words():
    assert data("https://аре.com/")["unicode"]["confusableCharacters"]  # "аре"
    ordinary = data("https://пример.com/")["unicode"]
    assert ordinary == {"mixedScriptLabels": [], "confusableCharacters": []}


def test_normal_japanese_mix_is_not_flagged():
    assert data("https://日本のサイト.com/")["unicode"] == {"mixedScriptLabels": [], "confusableCharacters": []}


def test_case_and_encoding_of_path_query_fragment_are_preserved():
    url = "HTTPS://WWW.Example.COM/A/b/%7Euser/../C?Token=AbC#Frag"
    result = data(url)
    assert result["address"]["normalizedUrl"] == "https://www.example.com/A/b/%7Euser/../C?Token=AbC#Frag"
    assert result["address"]["path"] == "/A/b/%7Euser/../C"
    assert result["features"]["pathDepth"] == 5
    assert result["features"]["hasPercentEncoding"] is True


def test_empty_and_repeated_query_parameters():
    result = data("https://example.com/?a=1&a=&b&&A=2")
    assert result["features"]["queryParameterCount"] == 4
    assert result["address"]["query"] == {
        "parameterCount": 4,
        "names": ["a", "b", "A"],
        "repeatedNames": ["a"],
        "emptyValueCount": 2,
    }


def test_default_and_explicit_ports():
    explicit_default = data("https://example.com:443/")
    assert explicit_default["features"]["hasExplicitPort"] is True
    assert explicit_default["address"]["normalizedUrl"] == "https://example.com/"
    assert "url-port" not in finding_ids("https://example.com:443/")
    assert "url-port" in finding_ids("https://example.com:8443/")


@pytest.mark.parametrize(("url", "normalized"), CASES["accepted"])
def test_shared_accepted_cases(url, normalized):
    assert parse_url(url).normalized == normalized


@pytest.mark.parametrize(
    ("url", "code"),
    [(url, code) for code, urls in CASES["rejected"].items() for url in urls] + CASES["serverOnlyRejections"],
)
def test_shared_rejected_cases(url, code):
    with pytest.raises(InvalidUrl) as error:
        parse_url(url)
    assert error.value.code == code


@pytest.mark.parametrize("url", CASES["rejected"]["credentials_not_allowed"])
def test_credential_rejection_does_not_repeat_the_input(url):
    with pytest.raises(InvalidUrl) as error:
        parse_url(url)
    assert "password" not in error.value.message and "p%40ss" not in str(error.value)


def test_percent_encoded_and_fullwidth_hostnames():
    assert parse_url("https://ex%41mple.com/").hostname == "example.com"
    assert parse_url("https://ｅｘａｍｐｌｅ。ｃｏｍ./").hostname == "example.com"


def test_no_reference_collection_is_unavailable_not_zero(tmp_path):
    assert data("https://example.com/")["reference"] == {
        "status": "unavailable",
        "reason": "not_configured",
        "collectionVersion": None,
        "collectionSize": 0,
        "match": None,
    }
    empty = tmp_path / "empty.json"
    empty.write_text('{"version": "v0", "domains": []}', encoding="utf-8")
    reference = data("https://example.com/", empty)["reference"]
    assert (reference["status"], reference["reason"], reference["match"]) == ("unavailable", "empty_collection", None)


@pytest.mark.parametrize("content", ["not json", "[]", '{"domains": []}', '{"version": 1, "domains": []}'])
def test_broken_reference_file_does_not_stop_inspection(tmp_path, content):
    path = tmp_path / "broken.json"
    path.write_text(content, encoding="utf-8")
    assert data("https://example.com/", path)["reference"]["reason"] == "load_error"
    assert data("https://example.com/", tmp_path / "missing.json")["reference"]["reason"] == "load_error"


def test_reference_entries_must_be_registered_domains(tmp_path):
    path = tmp_path / "list.json"
    path.write_text(
        json.dumps({"version": "v", "domains": ["EXAMPLE.org", "www.example.com", "https://example.net", 5]}),
        encoding="utf-8",
    )
    reference = data("https://example.org/", path)["reference"]
    assert reference["collectionSize"] == 1 and reference["match"]["exactMatch"]


@pytest.mark.parametrize("url", ["http://192.0.2.1/", "https://host.example.test/"])
def test_no_registered_domain_means_no_comparison(url):
    reference = data(url, FIXTURE)["reference"]
    assert (reference["status"], reference["reason"], reference["match"]) == ("unavailable", "no_registered_domain", None)


def test_similarity_values():
    # One substitution in 11 characters.
    match = data("https://examp1e.com/", FIXTURE)["reference"]["match"]
    assert match["reference"] == "example.com" and match["exactMatch"] is False
    assert match["levenshteinSimilarity"] == pytest.approx(1 - 1 / 11, abs=1e-4)
    # Jaro = (10/11 + 10/11 + 1) / 3; common prefix of 4 (the maximum) with weight 0.1.
    jaro = (10 / 11 + 10 / 11 + 1) / 3
    assert match["jaroWinklerSimilarity"] == pytest.approx(jaro + 4 * 0.1 * (1 - jaro), abs=1e-4)


def test_suffix_differences_are_preserved():
    match = data("https://example.co/", FIXTURE)["reference"]["match"]
    assert match["exactMatch"] is False and match["levenshteinSimilarity"] < 1


def test_exact_and_unrepresented_domains():
    exact = data("https://www.example.com/", FIXTURE)["reference"]
    assert exact["collectionVersion"] == "test-fixture-1"
    assert exact["match"]["exactMatch"] and exact["match"]["levenshteinSimilarity"] == 1
    assert "url-reference-exact" in finding_ids("https://www.example.com/", FIXTURE)

    other = data("https://zzzzqqqq.dev/", FIXTURE)["reference"]
    assert other["status"] == "available" and other["match"]["exactMatch"] is False


def test_all_findings_are_informational():
    result = inspect_url("http://a.exаmple.com:81/%41")
    assert result.findings and {finding["severity"] for finding in result.findings} == {"info"}


def test_no_network_access(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted")

    for name in ("getaddrinfo", "gethostbyname", "create_connection"):
        monkeypatch.setattr(socket, name, refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)

    # A fresh extractor, so its suffix list is loaded while the network is blocked.
    import tldextract

    from app.services.url_inspection import parsing

    monkeypatch.setattr(parsing, "_extract_suffix", tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None))
    for url in ("https://www.example.co.uk/a?b=1", "http://192.0.2.1/", "https://bücher.example.com/"):
        inspect_url(url, FIXTURE)
