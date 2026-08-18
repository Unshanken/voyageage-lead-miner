import asyncio
import email.utils
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from leadminer.config import Settings


@dataclass(slots=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    body: str | None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and self.body is not None and self.error_code is None


class HttpFetcher:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        global_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.settings = settings
        self.global_semaphore = global_semaphore or asyncio.Semaphore(
            settings.crawler_global_concurrency
        )
        self.domain_semaphore = asyncio.Semaphore(settings.crawler_domain_concurrency)
        self._external_client = client
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.crawler_request_timeout),
            follow_redirects=True,
            max_redirects=settings.crawler_max_redirects,
            headers={"User-Agent": settings.crawler_user_agent, "Accept": "text/html,*/*;q=0.1"},
        )

    async def close(self) -> None:
        if self._external_client is None:
            await self.client.aclose()

    async def fetch(self, url: str, *, allow_text: bool = False) -> FetchResult:
        async with self.global_semaphore, self.domain_semaphore:
            if self.settings.crawler_delay_seconds:
                await asyncio.sleep(self.settings.crawler_delay_seconds)
            return await self._fetch_with_retries(url, allow_text=allow_text)

    async def _fetch_with_retries(self, url: str, *, allow_text: bool) -> FetchResult:
        attempts = self.settings.crawler_max_retries + 1
        for attempt in range(attempts):
            try:
                result = await self._fetch_once(url, allow_text=allow_text)
            except httpx.TooManyRedirects as exc:
                return _error(url, "TOO_MANY_REDIRECTS", str(exc))
            except httpx.TimeoutException as exc:
                result = _error(url, "TIMEOUT", str(exc))
            except httpx.TransportError as exc:
                result = _error(url, "TRANSPORT_ERROR", str(exc))

            transient = result.status_code in {429, 500, 502, 503, 504} or result.error_code in {
                "TIMEOUT",
                "TRANSPORT_ERROR",
            }
            if not transient or attempt == attempts - 1:
                return result
            retry_after = _retry_after_seconds(result.error_message)
            await asyncio.sleep(
                min(
                    retry_after if retry_after is not None else 0.25 * (2**attempt),
                    self.settings.crawler_retry_after_max_seconds,
                )
            )
        return _error(url, "UNKNOWN", "Request attempts exhausted")

    async def _fetch_once(self, url: str, *, allow_text: bool) -> FetchResult:
        async with self.client.stream("GET", url) as response:
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if response.status_code != 200:
                detail = (
                    response.headers.get("retry-after") if response.status_code == 429 else None
                )
                return FetchResult(
                    requested_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type or None,
                    body=None,
                    error_code=f"HTTP_{response.status_code}",
                    error_message=detail,
                )
            allowed_types = {"text/html", "application/xhtml+xml"}
            if allow_text:
                allowed_types.update({"text/plain", "text/robots"})
            if content_type not in allowed_types:
                return FetchResult(
                    requested_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type or None,
                    body=None,
                    error_code="UNSUPPORTED_CONTENT_TYPE",
                    error_message=content_type or "missing content-type",
                )
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.settings.crawler_max_response_bytes:
                    return FetchResult(
                        requested_url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=content_type,
                        body=None,
                        error_code="RESPONSE_TOO_LARGE",
                        error_message=(
                            f"Response exceeded {self.settings.crawler_max_response_bytes} bytes"
                        ),
                    )
                chunks.append(chunk)
            encoding = response.encoding or "utf-8"
            body = b"".join(chunks).decode(encoding, errors="replace")
            return FetchResult(
                requested_url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                body=body,
            )


def _error(url: str, code: str, message: str) -> FetchResult:
    return FetchResult(url, url, None, None, None, code, message[:500])


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            target = email.utils.parsedate_to_datetime(value)
            return max(0, (target - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError):
            return None
