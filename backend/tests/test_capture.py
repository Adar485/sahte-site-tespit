"""Page capture: network guard, real Chromium against local fixtures, persistence and API."""

import asyncio
import struct
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import capture_fixtures
from app.db.base import Base, utcnow
from app.db.session import get_db
from app.main import app
from app.models import Analysis, PageCapture
from app.services import analyses
from app.services.capture import get_capture_manager
from app.services.capture.browser import CaptureConfig, capture_page
from app.services.capture.manager import CaptureManager, new_capture
from app.services.capture.network import DestinationRefused, NetworkPolicy, is_public_address
from app.services.capture.storage import ArtifactStore

ALL_FILES = {"screenshot.png", "page.html", "visible_text.txt"}


# --------------------------------------------------------------------------- #
# Network guard (no browser)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "127.8.9.1", "0.0.0.0", "10.1.2.3", "172.16.0.1", "172.31.255.255", "192.168.1.1", "169.254.169.254",
        "100.64.0.1", "192.0.2.1", "198.18.0.1", "198.51.100.7", "203.0.113.9", "224.0.0.1", "239.255.255.250", "240.0.0.1",
        "255.255.255.255", "168.63.129.16", "::", "::1", "fe80::1", "fc00::1", "fd12:3456::1", "ff02::1", "::ffff:127.0.0.1",
        "::ffff:8.8.8.8", "64:ff9b::7f00:1", "2002:7f00:1::1", "2001:0:1::1", "2001:db8::1", "3fff::1", "not-an-ip",
    ],
)
def test_non_public_addresses(address):
    assert not is_public_address(address)


@pytest.mark.parametrize("address", ["93.184.215.14", "8.8.8.8", "1.1.1.1", "172.32.0.1", "2606:4700::6810:84e5", "2a00:1450:4017::200e"])
def test_public_addresses(address):
    assert is_public_address(address)


def addresses(policy, host, port=80):
    return asyncio.run(policy.addresses_for(host, port))


def resolver_for(table):
    async def resolve(host, port):
        if host not in table:
            raise OSError("unknown")
        answer = table[host]
        return answer.pop(0) if answer and isinstance(answer[0], list) else answer

    return resolve


def test_policy_checks_every_resolved_address_and_ports():
    policy = NetworkPolicy(resolver=resolver_for({
        "ok.test": ["93.184.215.14"], "mixed.test": ["93.184.215.14", "10.0.0.5"], "private.test": ["192.168.0.2"], "v6.test": ["::1"],
    }))
    assert addresses(policy, "ok.test") == ["93.184.215.14"]
    for host, port in (("mixed.test", 80), ("private.test", 80), ("v6.test", 80), ("127.0.0.1", 80), ("::1", 80), ("ok.test", 22), ("ok.test", 3306)):
        with pytest.raises(DestinationRefused) as refused:
            addresses(policy, host, port)
        assert refused.value.reason == "destination_blocked", (host, port)
    with pytest.raises(DestinationRefused) as refused:
        addresses(policy, "missing.test")
    assert refused.value.reason == "dns_error"
    assert NetworkPolicy().test_destinations == {}  # nothing is exempt by default


def test_dns_rebinding_cannot_change_the_connected_address(monkeypatch):
    """The resolver answers public first and private afterwards; only checked answers are dialled."""
    from app.services.capture import network

    answers = [["93.184.215.14"], ["127.0.0.1"]]

    async def rebinding(host, port):
        return answers.pop(0) if len(answers) > 1 else answers[0]

    dialled = []

    async def fake_open(address, port, **kwargs):
        dialled.append(address)
        raise OSError("not really connecting")

    async def run():
        proxy = network.EgressProxy(NetworkPolicy(resolver=rebinding), max_download_bytes=1000)
        monkeypatch.setattr(network.asyncio, "open_connection", fake_open)
        await proxy._open("rebind.test", 80)  # first answer: public, dialled exactly
        await proxy._open("rebind.test", 80)  # second answer: private, refused
        return proxy

    proxy = asyncio.run(run())
    assert dialled == ["93.184.215.14"]
    assert proxy.failures[("rebind.test", 80)] == "destination_blocked"


# --------------------------------------------------------------------------- #
# Real browser against fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def web():
    fixtures = capture_fixtures.Fixtures()
    yield fixtures
    fixtures.close()


def policy_for(web) -> NetworkPolicy:
    return NetworkPolicy(
        # The private port is allowed on purpose: only the address check may protect it.
        allowed_ports=frozenset({80, 443, web.port, web.private_port}),
        test_destinations={("fixture.test", web.port): "127.0.0.1"},
        resolver=resolver_for({"internal.test": ["127.0.0.1"], "localhost": ["::1", "127.0.0.1"], "fixture.test": ["127.0.0.1"]}),
    )


FAST = CaptureConfig(navigation_timeout_s=5, total_timeout_s=25, settle_max_s=3)


@pytest.fixture
def capture(web, tmp_path):
    def run(url, config=FAST):
        web.private_hits.clear()
        web.public_requests.clear()
        outcome = asyncio.run(capture_page(url, tmp_path, config, policy_for(web)))
        assert web.private_hits == [], "a private destination was reached"
        return outcome

    return run


def read(tmp_path, name):
    return (tmp_path / name).read_text(encoding="utf-8")


def test_screenshot_html_and_text_with_javascript_content(web, capture, tmp_path):
    outcome = capture(web.url("/"))
    assert (outcome.status, outcome.error_code, outcome.files) == ("completed", None, ALL_FILES)
    assert outcome.http_status == 200 and outcome.final_url == web.url("/")
    png = (tmp_path / "screenshot.png").read_bytes()
    assert png.startswith(b"\x89PNG") and struct.unpack(">II", png[16:24]) == (1366, 768)
    html, text = read(tmp_path, "page.html"), read(tmp_path, "visible_text.txt")
    assert "JavaScript ile eklenen içerik" in text and "Statik başlık — çğıöşü" in text
    assert "gizli metin" not in text and "gizli metin" in html
    assert 'id="app">JavaScript ile eklenen içerik<' in html
    assert outcome.text_length == len(text)
    details = outcome.details
    assert details["strategy"] == "domcontentloaded+load+dom-stable" and details["viewport"] == {"width": 1366, "height": 768}
    assert details["consistent"] and set(details["artifactTimes"]) == {"screenshot", "html", "text"}
    assert details["signals"] == {"httpError": False, "blank": False, "captcha": False}
    assert details["title"] == "Fixture sayfası" and not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("path", ["/redirect", "/js-redirect"])
def test_redirects_update_the_final_url(web, capture, tmp_path, path):
    outcome = capture(web.url(path))
    assert outcome.status == "completed" and outcome.final_url.startswith(web.url("/landing"))
    assert outcome.details["redirectChain"][0] == web.url(path) and len(outcome.details["redirectChain"]) == 2
    assert "Varış sayfası" in read(tmp_path, "visible_text.txt")


@pytest.mark.parametrize(
    "target",
    ["http://127.0.0.1:{private}/s", "http://localhost:{private}/s", "http://[::1]:{private}/s", "http://internal.test:{private}/s",
     "http://0.0.0.0:{private}/s", "http://[::ffff:127.0.0.1]:{private}/s", "http://2130706433:{private}/s", "http://127.1:{private}/s",
     "http://192.168.1.1/s", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.1/", "http://[fd00::1]/", "https://127.0.0.1:{private}/s",
     "http://fixture.test:{private}/s"],
)
def test_private_destinations_are_blocked(web, capture, target):
    outcome = capture(target.format(private=web.private_port))
    assert (outcome.status, outcome.error_code, outcome.files, outcome.final_url) == ("failed", "destination_blocked", set(), None)


@pytest.mark.parametrize("route", ["/to/", "/jsto/"])
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "internal.test", "[::1]"])
def test_redirects_to_private_destinations_are_blocked(web, capture, tmp_path, route, host):
    outcome = capture(web.url(f"{route}http://{host}:{web.private_port}/secret"))
    assert (outcome.status, outcome.error_code, outcome.files) == ("failed", "destination_blocked", set())


def test_subresources_frames_popups_sockets_and_forms(web, capture, tmp_path):
    outcome = capture(web.url("/probe"))
    assert outcome.status in ("completed", "partial") and "screenshot.png" in outcome.files
    text = read(tmp_path, "visible_text.txt")
    assert "rtc=undefined transport=undefined" in text
    assert outcome.details["blockedDestinations"] >= 1  # the proxy refused the private targets
    paths = [path for _, path in web.public_requests]
    assert "/popup-public" not in paths and "/ws-public" not in paths
    assert ("POST", "/submit") not in web.public_requests and outcome.final_url == web.url("/probe")


@pytest.mark.parametrize("path", ["/download", "/json"])
def test_downloads_and_non_pages_are_rejected(web, capture, path):
    outcome = capture(web.url(path))
    assert (outcome.status, outcome.error_code, outcome.files) == ("failed", "unsupported_content", set())


def test_script_started_download_is_blocked(web, capture, tmp_path):
    outcome = capture(web.url("/auto-download"))
    assert "screenshot.png" in outcome.files and not any(path.suffix == ".exe" for path in tmp_path.rglob("*"))


def test_redirect_limit(web, capture):
    outcome = capture(web.url("/loop"))
    assert (outcome.status, outcome.error_code) == ("failed", "too_many_redirects")


def test_navigation_timeout(web, capture):
    outcome = capture(web.url("/slow"), CaptureConfig(navigation_timeout_s=2, total_timeout_s=20))
    assert (outcome.status, outcome.error_code, outcome.files) == ("failed", "timeout", set())


def test_unfinished_subresource_does_not_prevent_capture(web, capture):
    outcome = capture(web.url("/never-load"), CaptureConfig(navigation_timeout_s=5, total_timeout_s=25, settle_max_s=1.5))
    assert "visible_text.txt" in outcome.files


def test_total_timeout_is_controlled(web, capture):
    started = time.monotonic()
    outcome = capture(web.url("/freeze"), CaptureConfig(navigation_timeout_s=5, total_timeout_s=8, settle_max_s=1))
    assert time.monotonic() - started < 20
    assert outcome.status in ("partial", "failed") and outcome.error_code


def test_page_changing_during_capture_is_partial(web, capture):
    outcome = capture(web.url("/changing"))
    assert outcome.status == "partial" and outcome.details["consistent"] is False


@pytest.mark.parametrize(
    ("path", "status", "signal"), [("/notfound", 404, "httpError"), ("/blank", 200, "blank"), ("/captcha", 200, "captcha")]
)
def test_page_observations(web, capture, path, status, signal):
    outcome = capture(web.url(path))
    assert outcome.http_status == status and "screenshot.png" in outcome.files
    assert outcome.details["signals"][signal] is True


def test_size_limits(web, capture, tmp_path):
    outcome = capture(web.url("/big"), CaptureConfig(max_html_bytes=10_000, max_text_chars=1_000))
    assert (outcome.status, outcome.error_code) == ("partial", "too_large")
    assert outcome.files == {"screenshot.png", "visible_text.txt"} and not (tmp_path / "page.html").exists()
    assert len(read(tmp_path, "visible_text.txt")) == 1_000 and outcome.details["truncated"] == ["text"]
    assert capture(web.url("/big"), CaptureConfig(max_download_bytes=20_000)).error_code == "limit_exceeded"


def test_each_capture_starts_without_cookies(web, capture, tmp_path):
    for _ in range(2):
        capture(web.url("/echo-state"))
        assert "cookie=yok" in read(tmp_path, "visible_text.txt")


def test_browser_processes_are_closed_after_failures(web, capture):
    psutil = pytest.importorskip("psutil")

    def browsers():
        return [p for p in psutil.Process().children(recursive=True) if "chrome" in p.name().lower()]

    for path in ("/slow", "/download", "/loop"):
        capture(web.url(path), CaptureConfig(navigation_timeout_s=2, total_timeout_s=10))
    capture(web.url("/freeze"), CaptureConfig(navigation_timeout_s=5, total_timeout_s=6, settle_max_s=1))
    deadline = time.monotonic() + 10
    while browsers() and time.monotonic() < deadline:
        time.sleep(0.5)
    assert browsers() == []


# --------------------------------------------------------------------------- #
# Persistence and API
# --------------------------------------------------------------------------- #


@pytest.fixture
def stack(web, tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    store = ArtifactStore(tmp_path / "captures", 100 * 1024 * 1024)
    manager = CaptureManager(sessions, store, FAST, policy_for(web))
    monkeypatch.setattr(analyses, "artifact_store", lambda: store)

    def database():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_capture_manager] = lambda: manager
    yield TestClient(app), sessions, store, manager
    app.dependency_overrides.clear()
    manager.shutdown()
    engine.dispose()


def submit(stack, url):
    client, _, _, manager = stack
    response = client.post("/api/analyze", json={"url": url})
    assert response.status_code == 202
    manager.wait_idle()
    return response.json(), client.get(f"/api/result/{response.json()['id']}").json()


def test_submission_capture_files_and_database_agree(web, stack):
    client, sessions, store, _ = stack
    accepted, job = submit(stack, web.url("/redirect"))
    assert (accepted["state"], accepted["status"]) == ("running", "running")
    result = job["result"]
    assert (job["state"], result["status"], result["analysisMode"]) == ("done", "partial", "url_only")
    assert result["risk"] is result["modelVersion"] is result["failure"] is None
    assert result["finalUrl"] == web.url("/landing?x=1")
    assert result["modules"]["url"]["status"] == "completed" and result["modules"]["url"]["data"]
    assert {result["modules"][name]["status"] for name in ("visual", "text", "html")} == {"skipped"}
    capture = result["capture"]
    assert capture["status"] == "completed" and capture["redirected"] and capture["httpStatus"] == 200
    assert capture["artifacts"] == {"screenshot": True, "html": True, "text": True}
    assert "Varış sayfası" in capture["textPreview"] and "<h1>" not in str(result["capture"])

    with sessions() as session:
        row = session.query(PageCapture).one()
        assert row.analysis_id == accepted["id"] and row.final_url == result["finalUrl"]
        prefix = f"{accepted['id']}/{row.id}/"
        assert (row.screenshot_path, row.html_path, row.text_path) == (prefix + "screenshot.png", prefix + "page.html", prefix + "visible_text.txt")
        assert row.has_screenshot and row.has_html and row.has_text
        assert all(store.resolve(path) for path in (row.screenshot_path, row.html_path, row.text_path))
        assert row.duration_ms > 0 and row.started_at and row.completed_at

    image = client.get(capture["screenshotUrl"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png" and image.content.startswith(b"\x89PNG")
    assert image.headers["x-content-type-options"] == "nosniff"
    for bad in ("../../etc/passwd", "..%2F..%2F.env", "00000000-0000-0000-0000-000000000000", accepted["id"]):
        assert client.get(f"/api/captures/{bad}/screenshot").status_code == 404
    assert client.get(f"/api/captures/{capture['id']}/page.html").status_code == 404

    history = client.get("/api/history").json()["items"][0]
    assert (history["status"], history["riskLevel"], history["finalUrl"]) == ("partial", None, result["finalUrl"])

    # A file removed from disk is no longer reported as available.
    (store.root / accepted["id"] / capture["id"] / "screenshot.png").unlink()
    again = client.get(f"/api/result/{accepted['id']}").json()["result"]["capture"]
    assert again["artifacts"]["screenshot"] is False and again["screenshotUrl"] is None

    assert client.delete(f"/api/analyses/{accepted['id']}").status_code == 204
    assert not (store.root / accepted["id"]).exists()
    with sessions() as session:
        assert session.query(PageCapture).count() == 0


@pytest.mark.parametrize(("target", "code"), [("http://127.0.0.1/", "destination_blocked"), ("http://nowhere.example.test/", "dns_error")])
def test_failed_capture_keeps_url_results(web, stack, target, code):
    client, sessions, store, _ = stack
    _, job = submit(stack, target)
    result = job["result"]
    assert result["status"] == "partial" and result["risk"] is None and result["finalUrl"] is None
    assert result["modules"]["url"]["status"] == "completed" and result["modules"]["url"]["data"]["features"]
    capture = result["capture"]
    assert (capture["status"], capture["error"]["code"], capture["screenshotUrl"], capture["textPreview"]) == ("failed", code, None, None)
    assert capture["error"]["message"] and capture["artifacts"] == {"screenshot": False, "html": False, "text": False}
    assert not any(path.is_file() for path in store.root.rglob("*")) if store.root.exists() else True


def test_unexpected_capture_error_does_not_leave_running_records(web, stack, monkeypatch):
    from app.services.capture import manager as manager_module

    async def broken(*args):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(manager_module, "capture_page", broken)
    _, job = submit(stack, web.url("/"))
    assert job["state"] == "done" and job["result"]["capture"]["error"]["code"] == "unknown"
    assert "secret" not in str(job)


def test_busy_and_full_storage(web, stack):
    client, _, store, manager = stack
    manager.max_pending = 0
    body = client.post("/api/analyze", json={"url": web.url("/")}).json()
    assert body["state"] == "done"
    assert client.get(f"/api/result/{body['id']}").json()["result"]["capture"]["error"]["code"] == "busy"
    manager.max_pending, store.max_total_bytes = 10, 0
    _, job = submit(stack, web.url("/"))
    assert job["result"]["capture"]["error"]["code"] == "storage_full"


def test_credentials_are_rejected_before_any_capture(web, stack):
    client, sessions, _, _ = stack
    web.public_requests.clear()
    response = client.post("/api/analyze", json={"url": f"http://user:pw@fixture.test:{web.port}/"})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "credentials_not_allowed"
    with sessions() as session:
        assert session.query(Analysis).count() == 0 and session.query(PageCapture).count() == 0
    assert web.public_requests == []


def test_interrupted_captures_are_closed_at_startup(stack):
    client, sessions, store, manager = stack
    with sessions() as session:
        analysis = Analysis(submitted_url="https://example.com/", status="running", analysis_mode="url_only")
        analysis.capture = new_capture("https://example.com/")
        session.add(analysis)
        session.commit()
    store.staging(analysis.capture.id).joinpath("page.html.part").write_text("x")
    assert client.get(f"/api/result/{analysis.id}").json() == {
        "id": analysis.id, "state": "running", "stage": "page_fetch", "submittedUrl": "https://example.com/"
    }
    assert manager.recover_interrupted() == 1
    result = client.get(f"/api/result/{analysis.id}").json()["result"]
    assert result["status"] == "partial" and result["capture"]["error"]["code"] == "interrupted"
    assert not (store.root / ".staging").exists()


def test_shutdown_during_a_capture_closes_the_browser_and_the_record(web, stack):
    psutil = pytest.importorskip("psutil")

    def browsers():
        return [p for p in psutil.Process().children(recursive=True) if "chrome" in p.name().lower()]

    client, sessions, store, manager = stack
    body = client.post("/api/analyze", json={"url": web.url("/slow")}).json()
    deadline = time.monotonic() + 10
    while not browsers() and time.monotonic() < deadline:
        time.sleep(0.2)
    assert browsers(), "the capture browser did not start"
    manager.shutdown()
    deadline = time.monotonic() + 10
    while browsers() and time.monotonic() < deadline:
        time.sleep(0.2)
    assert browsers() == []
    result = client.get(f"/api/result/{body['id']}").json()["result"]
    assert result["status"] == "partial" and result["capture"]["error"]["code"] == "interrupted"
    assert not any(path.is_file() for path in store.root.rglob("*"))
    assert manager.submit("00000000-0000-0000-0000-000000000000") is False


def test_failed_file_write_is_never_reported_as_an_artifact(web, stack, monkeypatch):
    from app.services.capture import storage

    original = storage.write_file

    def disk_error(directory, name, data):
        if name == storage.HTML:
            raise OSError("disk full")
        original(directory, name, data)

    monkeypatch.setattr(storage, "write_file", disk_error)
    client, sessions, store, _ = stack
    _, job = submit(stack, web.url("/"))
    capture = job["result"]["capture"]
    assert capture["status"] == "partial" and capture["error"]["code"] == "unknown"
    assert capture["artifacts"] == {"screenshot": True, "html": False, "text": False}
    with sessions() as session:
        row = session.query(PageCapture).one()
        assert row.html_path is None and not row.has_html and store.resolve(row.screenshot_path)
    assert [path.name for path in store.root.rglob("*") if path.is_file()] == ["screenshot.png"]


def test_files_are_removed_when_the_record_cannot_be_saved(web, stack, monkeypatch):
    from app.services.capture import manager as manager_module

    def database_error(analysis):
        raise RuntimeError("commit failed")

    client, _, store, manager = stack
    original = manager_module.finish_analysis
    calls = []
    # Fails while saving the result, succeeds when the capture is then closed as failed.
    monkeypatch.setattr(manager_module, "finish_analysis", lambda a: database_error(a) if not calls.append(1) and len(calls) == 1 else original(a))
    _, job = submit(stack, web.url("/"))
    assert job["result"]["capture"]["error"]["code"] == "unknown"
    assert job["result"]["capture"]["artifacts"] == {"screenshot": False, "html": False, "text": False}
    assert not any(path.is_file() for path in store.root.rglob("*"))


def test_deleting_an_analysis_during_its_capture_leaves_no_files(web, stack):
    client, sessions, store, manager = stack
    body = client.post("/api/analyze", json={"url": web.url("/never-load")}).json()
    time.sleep(0.5)
    assert client.delete(f"/api/analyses/{body['id']}").status_code == 204
    manager.wait_idle()
    assert not any(path.is_file() for path in store.root.rglob("*"))
    with sessions() as session:
        assert session.query(PageCapture).count() == 0


def test_missing_browser_is_a_controlled_failure(web, stack, monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "no-browsers"))
    _, job = submit(stack, web.url("/"))
    result = job["result"]
    assert result["capture"]["error"]["code"] == "browser_unavailable"
    assert result["modules"]["url"]["status"] == "completed"


def test_older_records_without_capture_still_open(stack):
    client, sessions, _, _ = stack
    with sessions() as session:
        old = Analysis(submitted_url="https://example.com/", status="partial", analysis_mode="url_only", completed_at=utcnow())
        session.add(old)
        session.commit()
    result = client.get(f"/api/result/{old.id}").json()["result"]
    assert result["capture"] is None and result["status"] == "partial"


def test_database_refuses_an_artifact_flag_without_a_path(stack):
    _, sessions, _, _ = stack
    with sessions() as session:
        analysis = Analysis(submitted_url="https://example.com/", status="partial")
        analysis.capture = new_capture("https://example.com/")
        analysis.capture.has_screenshot = True
        session.add(analysis)
        with pytest.raises(IntegrityError):
            session.commit()
