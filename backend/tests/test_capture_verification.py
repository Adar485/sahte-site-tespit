"""Further capture checks: content correctness, regressions, routes, failures and cleanup."""

import asyncio
import time

import pytest
from PIL import Image
from sqlalchemy.exc import OperationalError

import capture_fixtures
from app.db.session import get_db
from app.main import app
from app.models import Analysis, PageCapture
from app.services.capture import browser as browser_module
from app.services.capture.browser import CaptureConfig, capture_page
from app.services.capture.manager import CaptureManager
from test_capture import FAST, capture, policy_for, stack, submit, web  # noqa: F401 - shared fixtures

# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #

UNICODE = "Çağrı İstanbul ışık — Ünicode: 日本語 · العربية · Ω · 🔒"


def test_known_page_content_pixels_and_unicode(web, capture, tmp_path):
    outcome = capture(web.url("/visual"))
    assert (outcome.status, outcome.error_code) == ("completed", None)
    text = (tmp_path / "visible_text.txt").read_bytes().decode("utf-8")
    html = (tmp_path / "page.html").read_bytes().decode("utf-8")
    for expected in ("Bilinen başlık", "Gövde metni burada.", UNICODE, "Betikle eklenen paragraf"):
        assert expected in text and expected in html, expected
    for absent in ("SCRIPT_SOURCE_MARKER", "STYLE_SOURCE_MARKER", "display-none içerik", "görünmez içerik", "noscript içerik"):
        assert absent not in text and absent in html, absent

    with Image.open(tmp_path / "screenshot.png") as image:
        image.verify()  # decodable, not truncated
    with Image.open(tmp_path / "screenshot.png") as image:
        pixels = image.convert("RGB")
        assert pixels.size == (1366, 768) and image.format == "PNG"
        assert pixels.getpixel((50, 50)) == (200, 0, 0)  # static block
        assert pixels.getpixel((50, 250)) == (0, 0, 200)  # block inserted by JavaScript after 600 ms
        assert pixels.getpixel((1300, 700)) == (255, 255, 255)
        assert len(pixels.getcolors(100_000)) > 20  # rendered glyphs, not a flat blank or loading screen


@pytest.mark.parametrize("path", ["/hidden-body", "/hidden-root"])
def test_unrendered_documents_yield_no_script_or_style_source(web, capture, tmp_path, path):
    outcome = capture(web.url(path))
    assert "visible_text.txt" in outcome.files
    assert (tmp_path / "visible_text.txt").read_text(encoding="utf-8") == ""
    assert "SCRIPT_SOURCE_MARKER" in (tmp_path / "page.html").read_text(encoding="utf-8")
    assert outcome.details["signals"]["blank"] is True  # nothing visible was rendered


def test_page_cannot_exceed_the_text_limit(web, capture, tmp_path):
    outcome = capture(web.url("/override-slice"), CaptureConfig(max_text_chars=1_000, settle_max_s=2))
    assert len((tmp_path / "visible_text.txt").read_text(encoding="utf-8")) == 1_000
    assert outcome.details["truncated"] == ["text"]


@pytest.mark.parametrize("mode", ["other-address", "same-address-reload"])
def test_navigation_between_artifacts_is_flagged(web, capture, monkeypatch, mode):
    from playwright.async_api import Page

    original = Page.content

    async def navigate_first(page):
        async with page.expect_navigation():
            await page.evaluate("location.href = '/landing'" if mode == "other-address" else "location.reload()")
        return await original(page)

    monkeypatch.setattr(Page, "content", navigate_first)
    outcome = capture(web.url("/"))
    assert outcome.status == "partial" and outcome.details["consistent"] is False
    times = outcome.details["artifactTimes"]
    assert times["screenshot"] <= times["html"] <= times["text"]


def test_redirect_chain_ends_at_the_real_final_url(web, capture):
    outcome = capture(web.url("/chain/3"))
    assert outcome.status == "completed" and outcome.final_url == web.url("/landing")
    assert len(outcome.details["redirectChain"]) == 5


@pytest.mark.parametrize("status", [404, 500])
def test_error_status_with_empty_body_is_not_a_success_claim(web, capture, status):
    outcome = capture(web.url(f"/empty/{status}"))
    assert outcome.http_status == status
    assert outcome.details["signals"] == {"httpError": True, "blank": True, "captcha": False}


def test_pdf_and_stalled_response(web, capture, tmp_path):
    assert capture(web.url("/pdf")).error_code == "unsupported_content"
    outcome = capture(web.url("/stall"), CaptureConfig(navigation_timeout_s=3, total_timeout_s=20, settle_max_s=1))
    assert (outcome.status, outcome.error_code) == ("partial", "timeout")
    assert "Yarım gövde" in (tmp_path / "visible_text.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Network channels
# --------------------------------------------------------------------------- #


def test_workers_and_frames_cannot_open_plain_websockets(web, capture):
    capture(web.url("/worker-sockets"))
    paths = [path for _, path in web.public_requests]
    assert "/worker-sockets" in paths
    assert not [path for path in paths if path.startswith("/socket-")], "a WebSocket reached the server"


@pytest.mark.parametrize("target", ["http://[fe80::1]/", "http://224.0.0.1/", "http://240.0.0.1/", "http://100.64.0.1/", "http://[ff02::1]/", "http://[::]/"])
def test_more_non_public_navigation_targets(web, capture, target):
    assert capture(target).error_code == "destination_blocked"


@pytest.mark.parametrize("scheme_target", ["file:///C:/Windows/win.ini", "data:text/html,<h1>x</h1>"])
def test_non_web_navigation_does_not_replace_the_page(web, capture, tmp_path, scheme_target):
    outcome = capture(web.url(f"/jsto/{scheme_target}"))
    assert outcome.final_url is None or outcome.final_url.startswith("http://fixture.test")
    for name in outcome.files - {"screenshot.png"}:
        assert "[fonts]" not in (tmp_path / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Routes, database failure, tampering
# --------------------------------------------------------------------------- #


def test_unknown_ids_and_invalid_routes(stack):
    client, *_ = stack
    missing = "00000000-0000-0000-0000-000000000000"
    result = client.get(f"/api/result/{missing}")
    assert result.status_code == 404 and result.json()["detail"]["code"] == "not_found"
    for identifier in (missing, "abc", "..", "%2e%2e%5c%2e%2e%5c.env", "a%00b"):
        response = client.get(f"/api/captures/{identifier}/screenshot")
        assert response.status_code == 404 and response.headers["content-type"] == "application/json"
        assert "sahte" not in response.text.lower() and "Traceback" not in response.text
    assert client.get(f"/api/captures/{missing}/screenshot").json()["detail"]["message"] == "Ekran görüntüsü bulunamadı."
    # Not routes at all: the framework's plain 404, nothing served from disk.
    for path in (f"/api/captures/{missing}/page.html", "/api/captures/..%2F..%2F.env/screenshot", "/var/captures/x"):
        assert client.get(path).status_code == 404


def test_stored_path_outside_the_storage_folder_is_not_served(web, stack, tmp_path):
    client, sessions, store, _ = stack
    _, job = submit(stack, web.url("/"))
    capture_id = job["result"]["capture"]["id"]
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    for value in ("../secret.txt", str(secret), "..\\secret.txt"):
        with sessions() as session:
            session.get(PageCapture, capture_id).screenshot_path = value
            session.commit()
        response = client.get(f"/api/captures/{capture_id}/screenshot")
        assert response.status_code == 404 and "TOP-SECRET" not in response.text
        assert client.get(f"/api/result/{job['id']}").json()["result"]["capture"]["screenshotUrl"] is None


def test_database_unavailable_on_capture_routes(stack):
    client, *_ = stack

    def broken():
        raise OperationalError("SELECT secret_sql", {}, Exception(2003, "host=internal user=root"))
        yield

    app.dependency_overrides[get_db] = broken
    for method, path in (("get", "/api/captures/x/screenshot"), ("get", "/api/result/x"), ("get", "/api/history"), ("delete", "/api/analyses/x")):
        response = getattr(client, method)(path)
        assert response.status_code == 503
        assert response.json() == {"detail": {"code": "database_unavailable", "message": "Veritabanına şu anda ulaşılamıyor."}}


def test_database_failure_after_files_are_written(web, stack, monkeypatch):
    """Every commit that would save the result fails: no file may stay behind."""
    client, sessions, store, manager = stack
    original = manager._record

    def record_with_dead_database(*args):
        real = manager.session_factory

        def dying():
            session = real()
            session.commit = lambda: (_ for _ in ()).throw(OperationalError("x", {}, Exception()))
            return session

        manager.session_factory = dying
        try:
            return original(*args)
        finally:
            manager.session_factory = real

    monkeypatch.setattr(manager, "_record", record_with_dead_database)
    _, job = submit(stack, web.url("/"))
    assert job["result"]["capture"]["status"] == "failed" and job["result"]["capture"]["error"]["code"] == "unknown"
    assert not any(path.is_file() for path in store.root.rglob("*"))


def test_database_down_for_the_whole_job_is_recovered_later(web, stack):
    client, sessions, store, manager = stack
    real = manager.session_factory

    def down():
        raise OperationalError("x", {}, Exception())

    manager.session_factory = down
    body = client.post("/api/analyze", json={"url": web.url("/")}).json()
    manager.wait_idle()
    assert client.get(f"/api/result/{body['id']}").json()["state"] == "running"  # nothing could be written
    manager.session_factory = real
    assert manager.recover_interrupted() == 1
    assert client.get(f"/api/result/{body['id']}").json()["result"]["capture"]["error"]["code"] == "interrupted"


def test_restart_keeps_finished_records_and_files(web, stack):
    client, sessions, store, manager = stack
    _, before = submit(stack, web.url("/"))
    files = {path.name: path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
    manager.shutdown()
    restarted = CaptureManager(sessions, store, FAST, policy_for(web))
    assert restarted.recover_interrupted() == 0
    assert client.get(f"/api/result/{before['id']}").json() == before
    assert {path.name: path.read_bytes() for path in store.root.rglob("*") if path.is_file()} == files


# --------------------------------------------------------------------------- #
# Concurrency, repetition, clean-up
# --------------------------------------------------------------------------- #


def test_concurrency_limit_and_pending_limit(web, stack, monkeypatch):
    from app.services.capture import manager as manager_module

    running, peak = [0], [0]

    async def slow_capture(url, directory, config, policy):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        await asyncio.sleep(0.5)
        running[0] -= 1
        return browser_module.CaptureOutcome(error_code="navigation_failed")

    monkeypatch.setattr(manager_module, "capture_page", slow_capture)
    client, sessions, _, manager = stack
    manager.concurrency, manager.max_pending = 2, 5
    ids = [client.post("/api/analyze", json={"url": web.url("/")}).json()["id"] for _ in range(8)]
    manager.wait_idle()
    codes = [client.get(f"/api/result/{i}").json()["result"]["capture"]["error"]["code"] for i in ids]
    assert peak[0] == 2
    assert sorted(codes) == ["busy"] * 3 + ["navigation_failed"] * 5
    assert len(set(ids)) == 8  # each submission is its own record


def test_repeated_captures_leave_no_processes_or_proxy_tasks(web, stack):
    psutil = pytest.importorskip("psutil")

    def children():
        return [p.name() for p in psutil.Process().children(recursive=True) if p.name().lower().startswith(("chrome", "node"))]

    client, sessions, store, manager = stack
    urls = [web.url(path) for path in ("/", "/pdf", "/loop", "/redirect", "/to/http://127.0.0.1/", "/visual")]
    ids = [client.post("/api/analyze", json={"url": url}).json()["id"] for url in urls]
    manager.wait_idle(150)
    deadline = time.monotonic() + 10
    while children() and time.monotonic() < deadline:
        time.sleep(0.3)
    assert children() == []

    async def open_tasks():
        return len([t for t in asyncio.all_tasks() if t is not asyncio.current_task() and "EgressProxy" in repr(t)])

    assert asyncio.run_coroutine_threadsafe(open_tasks(), manager._loop).result(5) == 0
    finals = [client.get(f"/api/result/{i}").json()["result"]["capture"]["status"] for i in ids]
    assert finals == ["completed", "failed", "failed", "completed", "failed", "completed"]
    assert not any((store.root / ".staging").iterdir())
