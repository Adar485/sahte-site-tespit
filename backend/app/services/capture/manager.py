"""Runs captures in the background and records them.

Captures run on their own thread with their own asyncio loop, so API requests are
never blocked. The separate loop also matters on Windows: uvicorn --reload uses a
loop that cannot start the browser process.
"""

import asyncio
import concurrent.futures
import logging
import sys
import threading
import time
from pathlib import Path
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import Analysis, AnalysisStatus, CaptureStatus, PageCapture
from app.services.visual_inspection import VisualInspection
from app.services.capture import storage
from app.services.capture.browser import (
    CAPTURE_VERSION,
    ERROR_MESSAGES,
    VIEWPORT,
    CaptureConfig,
    CaptureOutcome,
    capture_page,
)
from app.services.capture.network import NetworkPolicy
from app.services.capture.storage import ArtifactStore

logger = logging.getLogger(__name__)


def _ignore_connection_resets(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    # Windows reports every connection the browser drops mid-way; that is expected here.
    if not isinstance(context.get("exception"), ConnectionError):
        loop.default_exception_handler(context)


def new_capture(requested_url: str) -> PageCapture:
    return PageCapture(
        status=CaptureStatus.PENDING.value,
        requested_url=requested_url,
        requested_at=utcnow(),
        viewport_width=VIEWPORT["width"],
        viewport_height=VIEWPORT["height"],
        capture_version=CAPTURE_VERSION,
        has_screenshot=False,
        has_html=False,
        has_text=False,
    )


def fail_capture(capture: PageCapture, code: str) -> None:
    capture.status = CaptureStatus.FAILED.value
    capture.error_code = code
    capture.error_message = ERROR_MESSAGES[code]
    capture.completed_at = utcnow()


def finish_analysis(analysis: Analysis) -> None:
    """The capture is over. The parent stays "partial": URL results exist, no risk was assessed."""
    now = utcnow()
    if analysis.status in (AnalysisStatus.PENDING.value, AnalysisStatus.RUNNING.value):
        analysis.status = AnalysisStatus.PARTIAL.value
    analysis.completed_at = now
    analysis.duration_ms = max(0, int((now - analysis.created_at).total_seconds() * 1000))


class CaptureManager:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: ArtifactStore,
        config: CaptureConfig | None = None,
        policy: NetworkPolicy | None = None,
        concurrency: int = 2,
        max_pending: int = 10,
        visual_inspector: Callable[[Path | None], VisualInspection] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.store = store
        self.config = config or CaptureConfig()
        self.policy = policy or NetworkPolicy()
        self.concurrency = concurrency
        self.max_pending = max_pending
        self.visual_inspector = visual_inspector
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._slots: asyncio.Semaphore | None = None
        self._futures: set[concurrent.futures.Future] = set()
        self._jobs: set[asyncio.Task] = set()  # touched only on the capture loop
        self._closed = False

    # -- lifecycle ---------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
            loop.set_exception_handler(_ignore_connection_resets)
            self._thread = threading.Thread(target=loop.run_forever, name="page-capture", daemon=True)
            self._thread.start()
            self._loop = loop
        return self._loop

    def submit(self, capture_id: str) -> bool:
        """Queue a stored pending capture. False when too many are already waiting."""
        with self._lock:
            if self._closed or len(self._futures) >= self.max_pending:
                return False
            future = asyncio.run_coroutine_threadsafe(self._run(capture_id), self._ensure_loop())
            self._futures.add(future)
        future.add_done_callback(self._futures.discard)
        return True

    def wait_idle(self, timeout: float = 90) -> None:
        concurrent.futures.wait(list(self._futures), timeout=timeout)

    def shutdown(self, timeout: float = 20) -> None:
        """Cancel captures, wait for their browsers to close, stop the thread. Safe to repeat."""
        with self._lock:
            self._closed = True
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
        if loop is None or thread is None:
            return

        async def cancel_jobs() -> None:
            # Only our jobs: Playwright's own tasks must keep running so browsers can close.
            jobs = list(self._jobs)
            for job in jobs:
                job.cancel()
            if jobs:
                await asyncio.wait(jobs, timeout=timeout)

        try:
            asyncio.run_coroutine_threadsafe(cancel_jobs(), loop).result(timeout + 5)
        except Exception as error:  # noqa: BLE001
            logger.warning("Captures did not stop cleanly (%s).", type(error).__name__)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)

    # -- work --------------------------------------------------------------

    async def _run(self, capture_id: str) -> None:
        job = asyncio.current_task()
        assert job is not None
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)
        if self._slots is None:
            self._slots = asyncio.Semaphore(self.concurrency)
        try:
            async with self._slots:
                started = time.perf_counter()
                pending = await asyncio.to_thread(self._start, capture_id)
                if pending is None:
                    return
                analysis_id, url = pending
                if await asyncio.to_thread(self.store.is_full):
                    outcome = CaptureOutcome(error_code="storage_full")
                else:
                    outcome = await capture_page(url, self.store.staging(capture_id), self.config, self.policy)
                elapsed = int((time.perf_counter() - started) * 1000)
                await asyncio.to_thread(self._record, capture_id, analysis_id, outcome, elapsed)
        except asyncio.CancelledError:
            self._abandon(capture_id, "interrupted")
            raise
        except Exception as error:  # noqa: BLE001 - no record may stay "running"
            logger.error("Capture %s failed (%s).", capture_id, type(error).__name__)
            self._abandon(capture_id, "unknown")

    def _start(self, capture_id: str) -> tuple[str, str] | None:
        with self.session_factory() as session:
            capture = session.get(PageCapture, capture_id)
            if capture is None or capture.status != CaptureStatus.PENDING.value:
                return None
            capture.status = CaptureStatus.RUNNING.value
            capture.started_at = utcnow()
            session.commit()
            return capture.analysis_id, capture.requested_url

    def _record(self, capture_id: str, analysis_id: str, outcome: CaptureOutcome, elapsed_ms: int) -> None:
        relative = None
        if outcome.files:
            relative = self.store.commit(analysis_id, capture_id)
        else:
            self.store.discard(capture_id)

        try:
            # Runs on the worker thread, outside a DB transaction. The parent and
            # capture stay running until inference finishes; restart recovery still applies.
            visual = None
            if self.visual_inspector is not None:
                screenshot = self.store.resolve(f"{relative}/{storage.SCREENSHOT}") if relative and storage.SCREENSHOT in outcome.files else None
                try:
                    visual = self.visual_inspector(screenshot)
                except Exception as error:
                    logger.warning("Visual worker failed (%s).", type(error).__name__)
                    visual = VisualInspection("failed", "Görsel özellikler çıkarılamadı.", [], None,
                                              "Görsel analiz sırasında bir sorun oluştu.", 0)
            with self.session_factory() as session:
                capture = session.get(PageCapture, capture_id)
                if capture is None:  # the analysis was deleted meanwhile
                    self.store.delete_analysis(analysis_id)
                    return
                # A cancelled worker thread may finish after shutdown/recovery.
                if capture.status != CaptureStatus.RUNNING.value:
                    self.store.delete_analysis(analysis_id)
                    return

                def path(name: str) -> str | None:
                    if relative is None or name not in outcome.files or self.store.resolve(f"{relative}/{name}") is None:
                        return None
                    return f"{relative}/{name}"

                capture.screenshot_path, capture.html_path, capture.text_path = (
                    path(storage.SCREENSHOT), path(storage.HTML), path(storage.TEXT),
                )
                capture.has_screenshot = capture.screenshot_path is not None
                capture.has_html = capture.html_path is not None
                capture.has_text = capture.text_path is not None
                capture.text_length = outcome.text_length if capture.has_text else None
                capture.status = outcome.status
                capture.final_url = outcome.final_url
                capture.http_status = outcome.http_status
                capture.error_code = outcome.error_code
                capture.error_message = outcome.error_message
                capture.details = outcome.details or None
                capture.completed_at = utcnow()
                capture.duration_ms = elapsed_ms

                analysis = capture.analysis
                if visual is not None:
                    row = next((item for item in analysis.modules if item.module == "visual"), None)
                    if row is not None:
                        row.status, row.summary = visual.status, visual.summary
                        row.findings, row.features = visual.findings, visual.data
                        row.error_message, row.duration_ms = visual.error_message, visual.duration_ms
                        if visual.status == "completed":
                            analysis.analysis_mode = None
                if outcome.final_url:
                    analysis.final_url = outcome.final_url
                finish_analysis(analysis)
                session.commit()
        except Exception:
            self.store.delete_analysis(analysis_id)  # no files without a record of them
            raise
        logger.info("Capture %s finished: %s%s.", capture_id, outcome.status, f" ({outcome.error_code})" if outcome.error_code else "")

    def _abandon(self, capture_id: str, code: str) -> None:
        try:
            self.store.discard(capture_id)
            with self.session_factory() as session:
                capture = session.get(PageCapture, capture_id)
                if capture is None or capture.status not in (CaptureStatus.PENDING.value, CaptureStatus.RUNNING.value):
                    return
                fail_capture(capture, code)
                finish_analysis(capture.analysis)
                session.commit()
        except Exception as error:  # noqa: BLE001 - recovered at next startup
            logger.error("Capture %s could not be closed (%s).", capture_id, type(error).__name__)

    def recover_interrupted(self) -> int:
        """At startup: no capture from an earlier process can still be running."""
        self.store.discard_all_staging()
        with self.session_factory() as session:
            unfinished = session.execute(
                select(PageCapture).where(PageCapture.status.in_([CaptureStatus.PENDING.value, CaptureStatus.RUNNING.value]))
            ).scalars().all()
            for capture in unfinished:
                fail_capture(capture, "interrupted")
                finish_analysis(capture.analysis)
            session.commit()
        if unfinished:
            logger.warning("%d unfinished capture(s) from an earlier run marked as interrupted.", len(unfinished))
        return len(unfinished)
