"""Submit-and-poll client for the ai_tools RQ job queue.

ai_tools is asynchronous now: ``POST /ocr|/whisper|/anonymize`` returns
``202 {job_id, status_url}``; the result is fetched by polling
``GET /jobs/{id}`` until the status is ``done`` (→ result dict) or ``failed``.
There is no ``503`` to retry any more — the queue accepts every submit and
serialises the GPU work, so a client never gets rejected; it waits in line.

Error mapping (shared by the sync + async variants):

* transport error (connect/timeout/read) on submit or on any poll, a ``5xx``,
  or exceeding ``max_wait`` → :class:`DependencyUnavailable`. The run then WAITS
  and retries (and the caller's Wake-on-LAN path can wake the GPU box). This is
  the new equivalent of the old ``503 → DependencyUnavailable``.
* the job ran and ended ``failed``, a ``4xx`` on submit (bad input), or the job
  vanished (``404`` while polling, e.g. result TTL expired) →
  :class:`JobFailedError`. A real failure — callers may fall back (OCR →
  Tesseract) or surface an error.

Wake-on-LAN stays with the *callers* (they pre-wake the GPU node); this module
only maps a mid-flight outage to ``DependencyUnavailable``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, cast

import httpx

from syndicus_contracts.dependency import DependencyUnavailable

logger = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT = 60.0  # upload + 202, and each status GET
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_MAX_WAIT = 600.0  # OCR can take minutes; then escalate to WAIT + retry

_TRANSPORT_ERRORS = (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError)


class JobFailedError(RuntimeError):
    """The ai_tools job ran and ended in ``failed`` (or the submit was rejected
    / the job is gone). A real error — not a wait-and-retry condition."""


def _accepted_status_url(resp: httpx.Response, blocked_on: str) -> str:
    """Validate a submit response and return its ``status_url``."""
    if resp.status_code == 202:
        return cast(str, resp.json()["status_url"])
    if resp.status_code >= 500:
        raise DependencyUnavailable(blocked_on)  # server trouble enqueuing → wait
    detail: str
    try:
        detail = resp.json().get("detail", "")
    except Exception:
        detail = resp.text[:200]
    raise JobFailedError(f"ai_tools submit rejected ({resp.status_code}): {detail}")


def _interpret_status(
    resp: httpx.Response, blocked_on: str,
) -> tuple[bool, dict[str, Any] | None, int | None]:
    """Map a ``GET /jobs/{id}`` response → ``(done, result, position)``.

    Raises DependencyUnavailable on 5xx, JobFailedError on 404/failed.
    """
    if resp.status_code >= 500:
        raise DependencyUnavailable(blocked_on)
    if resp.status_code == 404:
        raise JobFailedError("ai_tools job not found (result expired or lost)")
    if resp.status_code != 200:
        raise JobFailedError(f"ai_tools job status HTTP {resp.status_code}")
    data = resp.json()
    status = data.get("status")
    if status == "done":
        return True, (data.get("result") or {}), None
    if status == "failed":
        raise JobFailedError(f"ai_tools job failed: {(data.get('error') or '')[:300]}")
    return False, None, data.get("position")


def submit_and_poll_sync(
    *,
    base_url: str,
    endpoint: str,
    files: dict[str, Any] | None = None,
    json: Any | None = None,
    headers: dict[str, Any] | None = None,
    http_timeout: float = DEFAULT_HTTP_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    max_wait: float = DEFAULT_MAX_WAIT,
    blocked_on: str = "ai_tools",
) -> dict[str, Any]:
    """Submit a job and block (``time.sleep``) until it finishes; return ``result``."""
    base = base_url.rstrip("/")
    with httpx.Client(base_url=base, timeout=http_timeout) as client:
        try:
            resp = client.post(endpoint, files=files, json=json, headers=headers)
        except _TRANSPORT_ERRORS as exc:
            raise DependencyUnavailable(blocked_on) from exc
        status_url = _accepted_status_url(resp, blocked_on)

        deadline = time.monotonic() + max_wait
        while True:
            time.sleep(poll_interval)
            try:
                sresp = client.get(status_url)
            except _TRANSPORT_ERRORS as exc:
                raise DependencyUnavailable(blocked_on) from exc
            done, result, _ = _interpret_status(sresp, blocked_on)
            if done:
                assert result is not None  # _interpret_status: done ⇒ result-Dict
                return result
            if time.monotonic() > deadline:
                logger.warning("ai_tools job exceeded %.0fs budget — escalating to wait", max_wait)
                raise DependencyUnavailable(blocked_on)


async def submit_and_poll_async(
    client: httpx.AsyncClient,
    endpoint: str,
    *,
    files: dict[str, Any] | None = None,
    json: Any | None = None,
    headers: dict[str, Any] | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    max_wait: float = DEFAULT_MAX_WAIT,
    blocked_on: str = "ai_tools",
    on_progress: Callable[[int | None, float], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Async submit-and-poll on a caller-provided client; return ``result``.

    ``on_progress(position, elapsed)`` (optional) is awaited after each poll that
    is still processing — lets the briefing pipeline stream the queue position.
    """
    try:
        resp = await client.post(endpoint, files=files, json=json, headers=headers)
    except _TRANSPORT_ERRORS as exc:
        raise DependencyUnavailable(blocked_on) from exc
    status_url = _accepted_status_url(resp, blocked_on)

    elapsed = 0.0
    while True:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        try:
            sresp = await client.get(status_url)
        except _TRANSPORT_ERRORS as exc:
            raise DependencyUnavailable(blocked_on) from exc
        done, result, position = _interpret_status(sresp, blocked_on)
        if done:
            assert result is not None  # _interpret_status: done ⇒ result-Dict
            return result
        if on_progress is not None:
            try:
                await on_progress(position, elapsed)
            except Exception:
                logger.exception("gpu job progress callback raised — continuing")
        if elapsed > max_wait:
            logger.warning("ai_tools job exceeded %.0fs budget — escalating to wait", max_wait)
            raise DependencyUnavailable(blocked_on)
