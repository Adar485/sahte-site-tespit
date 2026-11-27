"""One browser visit -> screenshot, rendered HTML and visible text.

Strategy "domcontentloaded+load+dom-stable" (recorded with every capture, so that
reference images can later be taken the same way):
1. navigate and wait for DOMContentLoaded (navigation timeout),
2. wait for the load event, then until text length and element count stop changing
   twice in a row (both within the settle budget; "networkidle" is not used),
3. take the viewport screenshot, then the HTML, then the visible body text.

Nothing is clicked or typed. Each capture uses its own browser process, proxy and
unauthenticated context, all closed afterwards.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.services.capture import storage
from app.services.capture.network import EgressProxy, NetworkPolicy

logger = logging.getLogger(__name__)

CAPTURE_VERSION = "1.1"  # 1.1: unrendered documents no longer yield script/style source as text
STRATEGY = "domcontentloaded+load+dom-stable"
VIEWPORT = {"width": 1366, "height": 768}
LOCALE = "tr-TR"
TIMEZONE = "Europe/Istanbul"
ARTIFACT_TIMEOUT_S = 10

ERROR_MESSAGES = {
    "destination_blocked": "Adres, yerel ya da izin verilmeyen bir ağ hedefine gittiği için sayfa açılmadı.",
    "dns_error": "Alan adı çözümlenemedi; sayfaya ulaşılamadı.",
    "connection_failed": "Sunucuya bağlanılamadı.",
    "tls_error": "Güvenli bağlantı kurulamadı (sertifika veya TLS hatası).",
    "timeout": "Sayfa belirlenen süre içinde yüklenmedi.",
    "too_many_redirects": "Sayfa çok fazla kez yönlendirdi.",
    "unsupported_content": "Adres bir web sayfası döndürmedi; dosya indirmeleri engellenir.",
    "unsupported_navigation": "Sayfa desteklenmeyen bir adrese yönlendirdi.",
    "limit_exceeded": "Sayfa, izin verilen veri veya bağlantı sınırını aştı.",
    "navigation_failed": "Sayfa açılamadı.",
    "browser_unavailable": "Yakalama tarayıcısı başlatılamadı.",
    "artifacts_failed": "Sayfa açıldı ancak içeriği alınamadı.",
    "too_large": "Sayfa içeriğinin bir bölümü boyut sınırını aştığı için kaydedilmedi.",
    "storage_full": "Yakalama depolama sınırı dolduğu için sayfa kaydedilmedi.",
    "busy": "Çok sayıda yakalama sürdüğü için sayfa şu anda açılamadı.",
    "interrupted": "Sayfa yakalama tamamlanmadan kesildi.",
    "unknown": "Sayfa yakalanırken beklenmeyen bir sorun oluştu.",
}

_CHALLENGE_HOSTS = ("hcaptcha.com", "challenges.cloudflare.com")
_BLOCKED_RESOURCE_TYPES = {"media", "eventsource", "websocket"}

# Removes APIs that could open connections outside the proxy, and popups.
_INIT_SCRIPT = """
for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'WebTransport']) {
  try { Object.defineProperty(window, name, { value: undefined, writable: false, configurable: false }); } catch (e) {}
}
window.open = () => null;
"""

_STATE_SCRIPT = """() => [document.body ? document.body.innerText.length : 0, document.getElementsByTagName('*').length]"""
# innerText of an element that is not rendered falls back to ALL its text, scripts and styles
# included. It is therefore read from the root element, and only if that is rendered.
_PAGE_SCRIPT = """(limit) => {
  const root = document.documentElement;
  const rendered = !!root && getComputedStyle(root).display !== 'none';
  const text = (rendered && document.body ? root.innerText : '') || '';
  return {
    text: text.slice(0, limit),
    length: text.length,
    htmlLength: document.documentElement ? document.documentElement.outerHTML.length : 0,
    title: String(document.title || '').slice(0, 300),
    blank: !text.trim() && !document.querySelector('img,svg,canvas,video,iframe,input,button,embed,object'),
    captchaWidget: !!document.querySelector('.g-recaptcha,.h-captcha,.cf-turnstile'),
    scrollY: Math.round(window.scrollY),
  };
}"""


@dataclass(frozen=True)
class CaptureConfig:
    navigation_timeout_s: float = 20
    total_timeout_s: float = 45
    settle_max_s: float = 5
    max_redirects: int = 10
    max_requests: int = 250
    max_download_bytes: int = 30 * 1024 * 1024
    max_html_bytes: int = 5 * 1024 * 1024
    max_text_chars: int = 500_000
    max_screenshot_bytes: int = 10 * 1024 * 1024


@dataclass
class CaptureOutcome:
    status: str = "failed"  # completed | partial | failed
    final_url: str | None = None
    http_status: int | None = None
    files: set[str] = field(default_factory=set)  # names actually written
    text_length: int | None = None
    error_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def error_message(self) -> str | None:
        return ERROR_MESSAGES.get(self.error_code) if self.error_code else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _without_credentials(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return urlunsplit(parts._replace(netloc=parts.netloc.rpartition("@")[2]))[:4096]


async def _ignore_closed(coroutine) -> None:  # type: ignore[no-untyped-def]
    """For clean-up calls that may race with the browser closing."""
    try:
        await coroutine
    except PlaywrightError:
        pass


def _destination(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    return (parts.hostname or "").rstrip("."), parts.port or (443 if parts.scheme == "https" else 80)


class _Visit:
    """State of one page visit, kept outside the coroutine so a timeout keeps what was obtained."""

    def __init__(self, url: str, directory: Path, config: CaptureConfig, outcome: CaptureOutcome) -> None:
        self.url = url
        self.directory = directory
        self.config = config
        self.outcome = outcome
        self.navigations: list[str] = []  # every main-frame navigation request, redirects included
        self.response = None  # last main-frame document response
        self.request_count = 0
        self.fatal: str | None = None
        self.counters = {"popupsClosed": 0, "downloadsBlocked": 0, "requestsAborted": 0}

    # -- event handlers ----------------------------------------------------

    def on_request(self, page, request) -> None:  # type: ignore[no-untyped-def]
        if request.is_navigation_request() and request.frame == page.main_frame:
            self.navigations.append(request.url)
            if len(self.navigations) > self.config.max_redirects + 1:
                self.fatal = self.fatal or "too_many_redirects"
            parts = urlsplit(request.url)
            if parts.scheme not in ("http", "https") or "@" in parts.netloc:
                self.fatal = self.fatal or "unsupported_navigation"

    def on_response(self, page, response) -> None:  # type: ignore[no-untyped-def]
        request = response.request
        if request.is_navigation_request() and request.frame == page.main_frame and not 300 <= response.status < 400:
            self.response = response

    async def route(self, page, route) -> None:  # type: ignore[no-untyped-def]
        request = route.request
        self.request_count += 1
        parts = urlsplit(request.url)
        try:
            same_page = request.frame.page == page
        except PlaywrightError:  # a popup's first request has no frame yet
            same_page = False
        navigation = request.is_navigation_request()
        refused = (
            not same_page
            or self.request_count > self.config.max_requests
            or parts.scheme not in ("http", "https")
            or "@" in parts.netloc
            or request.resource_type in _BLOCKED_RESOURCE_TYPES
            # A page must not submit forms from our browser.
            or (navigation and request.method not in ("GET", "HEAD"))
            or (navigation and self.fatal == "too_many_redirects")
        )
        try:
            if refused:
                self.counters["requestsAborted"] += 1
                if navigation and request.url in self.navigations:
                    self.navigations.remove(request.url)  # it never happened: not part of the chain
                # "aborted" leaves the current page in place instead of showing an error page.
                await route.abort("aborted" if navigation else "blockedbyclient")
            else:
                await route.continue_()
        except PlaywrightError:
            pass  # the page was closed meanwhile

    # -- classification ----------------------------------------------------

    def navigation_problem(self, proxy: EgressProxy, error: str = "") -> str | None:
        """Why a main-frame navigation did not work, preferring what the proxy saw."""
        for url in self.navigations:
            reason = proxy.failures.get(_destination(url))
            if reason == "destination_blocked":
                return reason
        if proxy.limit_exceeded:
            return "limit_exceeded"
        if self.fatal:
            return self.fatal
        if not error:
            return None
        if self.navigations and (reason := proxy.failures.get(_destination(self.navigations[-1]))):
            return reason
        if "Download is starting" in error:
            return "unsupported_content"
        if "ERR_TOO_MANY_REDIRECTS" in error:
            return "too_many_redirects"
        if "ERR_CERT" in error or "ERR_SSL" in error:
            return "tls_error"
        if "Timeout" in error:
            return "timeout"
        if "ERR_UNSAFE" in error:
            return "destination_blocked"
        return "navigation_failed"


async def _settle(page, config: CaptureConfig) -> bool:  # type: ignore[no-untyped-def]
    """Wait for load and a quiet DOM within the budget. Returns whether it became stable."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + config.settle_max_s
    try:
        await page.wait_for_load_state("load", timeout=config.settle_max_s * 1000)
    except PlaywrightError:
        pass
    previous, unchanged = None, 0
    while loop.time() < deadline:
        await asyncio.sleep(0.4)
        try:
            current = await asyncio.wait_for(page.evaluate(_STATE_SCRIPT), 2)
        except (PlaywrightError, asyncio.TimeoutError):
            current = None
        unchanged = unchanged + 1 if current is not None and current == previous else 0
        if unchanged >= 2:
            return True
        previous = current
    return False


def _page_info(raw: Any, limit: int) -> dict[str, Any] | None:
    """The page computed these values, and it can redefine anything it uses: enforce types and limits here."""
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
        return None

    def number(key: str) -> int:
        value = raw.get(key)
        return int(value) if isinstance(value, (int, float)) and 0 <= value < 2**31 else 0

    return {
        "text": raw["text"][:limit],
        "length": max(number("length"), len(raw["text"])),
        "htmlLength": number("htmlLength"),
        "title": str(raw.get("title") or "")[:300],
        "blank": raw.get("blank") is True,
        "captchaWidget": raw.get("captchaWidget") is True,
        "scrollY": number("scrollY"),
    }


async def _artifacts(page, visit: _Visit) -> None:  # type: ignore[no-untyped-def]
    outcome, config, details = visit.outcome, visit.config, visit.outcome.details
    details["artifactTimes"], details["truncated"], details["skipped"] = {}, [], []

    def written(name: str, key: str, data: bytes) -> None:
        storage.write_file(visit.directory, name, data)
        outcome.files.add(name)
        details["artifactTimes"][key] = _now()

    async def attempt(coroutine):  # type: ignore[no-untyped-def]
        try:
            return await asyncio.wait_for(coroutine, ARTIFACT_TIMEOUT_S)
        except (PlaywrightError, asyncio.TimeoutError) as error:
            logger.info("Artifact could not be obtained (%s).", type(error).__name__)
            return None

    # performance.timeOrigin changes when a new document replaces this one, even at the same URL.
    start_navigations, start_url = len(visit.navigations), page.url
    start_document = await attempt(page.evaluate("() => performance.timeOrigin"))

    image = await attempt(page.screenshot(type="png", full_page=False, animations="disabled", caret="hide"))
    if image is not None:
        if len(image) <= config.max_screenshot_bytes:
            written(storage.SCREENSHOT, "screenshot", image)
        else:
            details["skipped"].append("screenshot")

    async def read_page() -> dict[str, Any] | None:
        return _page_info(await attempt(page.evaluate(_PAGE_SCRIPT, config.max_text_chars)), config.max_text_chars)

    info = await read_page()
    # Size is checked in the page first so a huge document is never transferred.
    if info is None or info["htmlLength"] <= config.max_html_bytes:
        html = await attempt(page.content())
        if html is not None:
            data = html.encode("utf-8", errors="replace")
            if len(data) <= config.max_html_bytes:
                written(storage.HTML, "html", data)
            else:
                details["skipped"].append("html")
    else:
        details["skipped"].append("html")

    # Read the text again after the HTML so it is as close in time as possible.
    info = await read_page() or info
    if info is not None:
        written(storage.TEXT, "text", info["text"].encode("utf-8", errors="replace"))
        outcome.text_length = info["length"]
        if info["length"] > config.max_text_chars:
            details["truncated"].append("text")
        details["title"] = info["title"]
        details["scrollY"] = info["scrollY"]
        details["signals"]["blank"] = info["blank"]
        details["signals"]["captcha"] = details["signals"]["captcha"] or info["captchaWidget"]

    end_document = await attempt(page.evaluate("() => performance.timeOrigin"))
    details["consistent"] = (
        len(visit.navigations) == start_navigations
        and page.url == start_url
        and start_document is not None
        and end_document == start_document
    )


async def _visit(visit: _Visit, proxy: EgressProxy) -> None:
    config, outcome = visit.config, visit.outcome
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                chromium_sandbox=True,  # Playwright's default is --no-sandbox
                proxy={"server": proxy.url, "bypass": "<-loopback>"},  # loopback goes to the proxy too
                args=[
                    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",  # no DNS in the browser
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--disable-quic",
                    "--no-pings",
                ],
                timeout=15_000,
            )
        except PlaywrightError as error:
            logger.error("Capture browser could not start (%s).", type(error).__name__)
            outcome.error_code = "browser_unavailable"
            return
        try:
            outcome.details["browser"] = f"chromium {browser.version}"
            context = await browser.new_context(
                viewport=VIEWPORT,
                device_scale_factor=1,
                locale=LOCALE,
                timezone_id=TIMEZONE,
                color_scheme="light",
                reduced_motion="reduce",
                accept_downloads=False,
                service_workers="block",
                ignore_https_errors=False,
            )
            await context.add_init_script(_INIT_SCRIPT)
            page = await context.new_page()
            page.set_default_timeout(ARTIFACT_TIMEOUT_S * 1000)

            def on_new_page(other) -> None:  # type: ignore[no-untyped-def]
                if other != page:
                    visit.counters["popupsClosed"] += 1
                    asyncio.ensure_future(_ignore_closed(other.close()))

            def on_download(download) -> None:  # type: ignore[no-untyped-def]
                visit.counters["downloadsBlocked"] += 1
                asyncio.ensure_future(_ignore_closed(download.cancel()))

            context.on("page", on_new_page)
            page.on("download", on_download)
            page.on("request", lambda request: visit.on_request(page, request))
            page.on("response", lambda response: visit.on_response(page, response))
            await context.route("**/*", lambda route: visit.route(page, route))
            # Handled without connecting to the server: WebSockets are closed at once.
            await context.route_web_socket("**/*", lambda socket: socket.close())

            error = ""
            try:
                await page.goto(visit.url, wait_until="domcontentloaded", timeout=config.navigation_timeout_s * 1000)
            except PlaywrightError as caught:
                error = str(caught)  # not logged: it repeats the address

            problem = visit.navigation_problem(proxy, error)
            # After a timeout a page that did answer can still be captured, as partial.
            if problem and not (problem == "timeout" and visit.response is not None):
                outcome.error_code = problem
                return
            if visit.response is None:
                outcome.error_code = problem or "navigation_failed"
                return
            content_type = (await visit.response.header_value("content-type") or "").split(";")[0].strip().lower()
            if content_type and not (content_type.startswith("text/") or content_type == "application/xhtml+xml"):
                outcome.error_code = "unsupported_content"
                return

            stable = await _settle(page, config)
            problem = visit.navigation_problem(proxy)  # script redirects during settling
            if problem or not page.url.startswith(("http://", "https://")):
                outcome.error_code = problem or visit.navigation_problem(proxy, "failed") or "unsupported_navigation"
                return

            response = visit.response
            challenge = await response.header_value("cf-mitigated") == "challenge" or any(
                _destination(frame.url)[0].endswith(_CHALLENGE_HOSTS) or "/recaptcha/" in frame.url
                for frame in page.frames[1:]
                if frame.url.startswith("http")
            )
            outcome.final_url = _without_credentials(page.url)
            outcome.http_status = response.status
            outcome.details["settled"] = stable
            outcome.details["signals"] = {"httpError": response.status >= 400, "blank": False, "captcha": challenge}
            if error:
                outcome.error_code = "timeout"

            await _artifacts(page, visit)

            outcome.final_url = _without_credentials(page.url) or outcome.final_url
            outcome.http_status = visit.response.status  # same navigation as final_url
            blocked = visit.navigation_problem(proxy)
            if blocked or not page.url.startswith(("http://", "https://")):
                outcome.files.clear()
                outcome.final_url = None
                outcome.error_code = blocked or "unsupported_navigation"
        finally:
            await browser.close()  # closes the context and every page


async def capture_page(url: str, directory: Path, config: CaptureConfig, policy: NetworkPolicy) -> CaptureOutcome:
    """Capture an already validated http(s) URL into directory. Never raises for page problems."""
    outcome = CaptureOutcome()
    outcome.details = {"strategy": STRATEGY, "viewport": VIEWPORT, "locale": LOCALE, "timezone": TIMEZONE}
    visit = _Visit(url, directory, config, outcome)
    async with EgressProxy(policy, config.max_download_bytes) as proxy:
        try:
            await asyncio.wait_for(_visit(visit, proxy), config.total_timeout_s)
        except asyncio.TimeoutError:
            outcome.error_code = visit.navigation_problem(proxy) or "timeout"
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - stored with a fixed message
            logger.error("Capture failed unexpectedly (%s).", type(error).__name__)
            outcome.error_code = visit.navigation_problem(proxy) or "unknown"
        outcome.details.update(
            redirectChain=[_without_credentials(item) for item in visit.navigations[: config.max_redirects + 1]],
            requestCount=visit.request_count,
            blockedDestinations=proxy.blocked_count,
            **visit.counters,
        )

    if outcome.error_code == "destination_blocked":
        outcome.files.clear()
        outcome.final_url = None
    complete = outcome.files == {storage.SCREENSHOT, storage.HTML, storage.TEXT}
    if complete and not outcome.error_code and outcome.details.get("consistent"):
        outcome.status = "completed"
    elif outcome.files:
        outcome.status = "partial"
        if not complete and not outcome.error_code:
            outcome.error_code = "too_large" if outcome.details.get("skipped") else "artifacts_failed"
    else:
        outcome.status = "failed"
        outcome.error_code = outcome.error_code or ("too_large" if outcome.details.get("skipped") else "artifacts_failed")
    return outcome
