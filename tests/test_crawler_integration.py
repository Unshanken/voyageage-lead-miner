import httpx
import pytest
from leadminer.config import Settings
from leadminer.crawler.fetcher import HttpFetcher
from leadminer.crawler.service import crawl_company
from leadminer.models import (
    Company,
    CrawledPage,
    CrawlStatus,
    PageCrawlStatus,
    SignalEvidence,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def html(body: str, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        text=body,
        headers={"content-type": "text/html", **(headers or {})},
    )


def settings(**overrides) -> Settings:
    values = {
        "crawler_delay_seconds": 0,
        "crawler_max_retries": 0,
        "crawler_max_pages_per_domain": 2,
        "crawler_domain_concurrency": 2,
    }
    values.update(overrides)
    return Settings(**values)


def company(session: Session, domain: str = "example.test") -> Company:
    item = Company(domain=domain, website_url=f"https://{domain}", company_name="Fixture")
    session.add(item)
    session.commit()
    return item


@pytest.mark.asyncio
async def test_home_discovers_docs_detects_anthropic_and_persists(session: Session) -> None:
    item = company(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
            )
        if request.url.path == "/":
            return html("<h1>Fixture</h1><a href='/docs'>Developer docs</a>")
        if request.url.path == "/docs":
            return html("<h1>Anthropic integration</h1><p>Set ANTHROPIC_API_KEY for Claude.</p>")
        return html("not found", 404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        report = await crawl_company(session, item.id, settings=settings(), client=client)

    session.refresh(item)
    assert report.status == CrawlStatus.CRAWLED
    assert item.anthropic_detected is True
    assert item.claude_detected is True
    assert item.llm_integration_signal is True
    assert session.scalar(select(func.count()).select_from(CrawledPage)) == 2
    assert session.scalar(select(func.count()).select_from(SignalEvidence)) >= 3


@pytest.mark.asyncio
async def test_robots_exclusion_is_persisted_without_fetch(session: Session) -> None:
    item = company(session)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /api",
                headers={"content-type": "text/plain"},
            )
        if request.url.path == "/":
            return html("<h1>Home</h1><a href='/api'>API</a>")
        raise AssertionError("Disallowed page was fetched")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await crawl_company(session, item.id, settings=settings(), client=client)

    skipped = session.scalar(
        select(CrawledPage).where(CrawledPage.crawl_status == PageCrawlStatus.SKIPPED)
    )
    assert skipped is not None
    assert skipped.error_code == "ROBOTS_DISALLOWED"
    assert "/api" not in requested
    assert report.pages_skipped == 1


@pytest.mark.asyncio
async def test_homepage_timeout_marks_company_failed(session: Session) -> None:
    item = company(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"})
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await crawl_company(session, item.id, settings=settings(), client=client)
    assert report.status == CrawlStatus.FAILED
    assert "TIMEOUT" in report.errors


@pytest.mark.asyncio
async def test_redirect_and_response_limit_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"})
        return html("<h1>Final</h1>")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        fetcher = HttpFetcher(settings(crawler_max_response_bytes=100_000), client)
        result = await fetcher.fetch("https://example.test/start")
    assert result.ok
    assert result.final_url == "https://example.test/final"


@pytest.mark.asyncio
async def test_cross_domain_redirect_is_not_extracted(session: Session) -> None:
    item = company(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"})
        if request.url.host == "example.test" and request.url.path == "/":
            return httpx.Response(302, headers={"location": "https://unrelated.test/"})
        return html("<h1>OpenAI</h1><p>Set OPENAI_API_KEY</p>")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        report = await crawl_company(session, item.id, settings=settings(), client=client)
    assert report.status == CrawlStatus.FAILED
    page = session.scalar(select(CrawledPage))
    assert page is not None
    assert page.error_code == "REDIRECT_DOMAIN_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_failed_recrawl_removes_stale_page_evidence(session: Session) -> None:
    item = company(session)
    redirect = False

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"})
        if redirect and request.url.host == "example.test":
            return httpx.Response(302, headers={"location": "https://unrelated.test/"})
        return html("<h1>OpenAI integration</h1><p>Set OPENAI_API_KEY.</p>")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        await crawl_company(
            session, item.id, settings=settings(crawler_max_pages_per_domain=1), client=client
        )
        assert session.scalar(select(func.count()).select_from(SignalEvidence)) > 0
        redirect = True
        await crawl_company(
            session,
            item.id,
            force=True,
            settings=settings(crawler_max_pages_per_domain=1),
            client=client,
        )

    assert session.scalar(select(func.count()).select_from(SignalEvidence)) == 0
    session.refresh(item)
    assert item.strong_ai_signal_count == 0


@pytest.mark.asyncio
async def test_response_size_and_content_type_are_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/binary":
            return httpx.Response(200, content=b"data", headers={"content-type": "image/png"})
        return httpx.Response(
            200,
            content=b"x" * 100_001,
            headers={"content-type": "text/html"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = HttpFetcher(settings(crawler_max_response_bytes=100_000), client)
        binary = await fetcher.fetch("https://example.test/binary")
        large = await fetcher.fetch("https://example.test/large")
    assert binary.error_code == "UNSUPPORTED_CONTENT_TYPE"
    assert large.error_code == "RESPONSE_TOO_LARGE"


@pytest.mark.asyncio
async def test_page_limit_and_force_recrawl_deduplicate_evidence(session: Session) -> None:
    item = company(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"})
        if request.url.path == "/":
            return html("<a href='/docs'>Docs</a><a href='/pricing'>Pricing</a>")
        return html("<h1>OpenAI docs</h1><p>Set OPENAI_API_KEY.</p>")

    active = settings(crawler_max_pages_per_domain=2)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await crawl_company(session, item.id, settings=active, client=client)
        first_count = session.scalar(select(func.count()).select_from(SignalEvidence))
        await crawl_company(session, item.id, force=True, settings=active, client=client)
    assert session.scalar(select(func.count()).select_from(CrawledPage)) == 2
    assert session.scalar(select(func.count()).select_from(SignalEvidence)) == first_count


@pytest.mark.asyncio
async def test_redirected_duplicate_content_is_only_counted_once(session: Session) -> None:
    item = company(session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"content-type": "text/plain"})
        if request.url.path == "/":
            return html("<a href='/docs'>Docs</a><a href='/docs/start'>Start</a>")
        if request.url.path == "/docs":
            return httpx.Response(308, headers={"location": "/docs/start"})
        return html("<h1>OpenAI docs</h1><p>Set OPENAI_API_KEY.</p>")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        report = await crawl_company(
            session,
            item.id,
            settings=settings(crawler_max_pages_per_domain=3),
            client=client,
        )

    assert report.pages_crawled == 2
    assert report.pages_skipped == 1
    duplicate = session.scalar(
        select(CrawledPage).where(CrawledPage.error_code == "DUPLICATE_CONTENT")
    )
    assert duplicate is not None
    evidence_pages = session.scalars(select(SignalEvidence.page_id).distinct()).all()
    assert len(evidence_pages) == 1
