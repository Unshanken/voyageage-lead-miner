import asyncio
import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from leadminer.config import Settings, get_settings
from leadminer.crawler.extract import ExtractedPage, extract_html
from leadminer.crawler.fetcher import HttpFetcher
from leadminer.crawler.robots import RobotsPolicy, fetch_robots
from leadminer.crawler.urls import (
    HIGH_VALUE_PATHS,
    canonicalize_url,
    classify_page,
    is_allowed_company_url,
    page_priority,
)
from leadminer.database import SessionLocal, create_database
from leadminer.models import (
    Company,
    CrawledPage,
    CrawlStatus,
    EmailClassification,
    PageCrawlStatus,
    PageType,
    PipelineStatus,
    PublishedEmail,
    SignalEvidence,
)
from leadminer.signals import DetectedSignal, detect_signals

logger = logging.getLogger("leadminer.crawler")
logger.setLevel(logging.INFO)


@dataclass(slots=True)
class CrawlReport:
    company_id: int
    domain: str
    status: CrawlStatus
    pages_crawled: int
    pages_failed: int
    pages_skipped: int
    strong_signals: int
    weak_signals: int
    providers: list[str]
    models: list[str]
    errors: list[str]
    fresh_skip: bool = False


@dataclass(slots=True)
class ProcessedPage:
    page: CrawledPage
    extracted: ExtractedPage | None


async def crawl_company(
    session: Session,
    company_id: int,
    *,
    force: bool = False,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
    global_semaphore: asyncio.Semaphore | None = None,
) -> CrawlReport:
    active_settings = settings or get_settings()
    company = session.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found")
    if not force and _is_fresh(company, active_settings):
        summary = company.crawl_summary or {}
        return CrawlReport(
            company.id,
            company.domain,
            CrawlStatus.FRESH,
            summary.get("pages_crawled", 0),
            summary.get("pages_failed", 0),
            summary.get("pages_skipped", 0),
            company.strong_ai_signal_count,
            company.weak_ai_signal_count,
            company.providers_detected,
            company.models_detected,
            summary.get("errors", []),
            fresh_skip=True,
        )

    company.crawl_status = CrawlStatus.CRAWLING
    company.pipeline_status = PipelineStatus.CRAWLING
    company.error_message = None
    session.commit()
    logger.info("company=%s event=crawl_started", company.domain)
    started = time.perf_counter()
    fetcher = HttpFetcher(active_settings, client, global_semaphore)
    errors: list[str] = []
    pages: list[ProcessedPage] = []
    try:
        robots = await fetch_robots(fetcher, company.website_url, active_settings)
        logger.info(
            "company=%s event=robots_checked status=%s error=%s",
            company.domain,
            robots.status,
            robots.error or "none",
        )
        homepage = canonicalize_url(company.website_url)
        if homepage is None:
            return _fail_company(session, company, started, ["INVALID_HOMEPAGE"], robots)
        home_result = await _process_page(
            session, company, homepage, 0, None, robots, fetcher, active_settings
        )
        pages.append(home_result)
        if home_result.page.crawl_status != PageCrawlStatus.FETCHED:
            return _fail_company(
                session,
                company,
                started,
                [home_result.page.error_code or "HOMEPAGE_FAILED"],
                robots,
            )

        candidates: dict[str, tuple[int, str | None, int]] = {}
        if home_result.extracted:
            for link in home_result.extracted.internal_links:
                _add_candidate(candidates, link, homepage, 1)
        base = homepage.rstrip("/")
        for path in HIGH_VALUE_PATHS:
            _add_candidate(candidates, f"{base}{path}", None, 1)
        candidates.pop(homepage, None)
        visited = {homepage}
        seen_final_urls = {canonicalize_url(home_result.page.url) or home_result.page.url}
        seen_content_hashes = (
            {home_result.page.content_hash} if home_result.page.content_hash else set()
        )

        while candidates and len(pages) < active_settings.crawler_max_pages_per_domain:
            ranked = sorted(candidates.items(), key=lambda item: (-item[1][0], item[0]))[
                : active_settings.crawler_domain_concurrency
            ]
            for url, _ in ranked:
                candidates.pop(url, None)
            remaining = active_settings.crawler_max_pages_per_domain - len(pages)
            ranked = ranked[:remaining]
            batch = await asyncio.gather(
                *[
                    _process_page(
                        session,
                        company,
                        url,
                        metadata[2],
                        metadata[1],
                        robots,
                        fetcher,
                        active_settings,
                    )
                    for url, metadata in ranked
                ]
            )
            for result in batch:
                final_url = canonicalize_url(result.page.url) or result.page.url
                duplicate = result.page.crawl_status == PageCrawlStatus.FETCHED and (
                    final_url in seen_final_urls
                    or (
                        result.page.content_hash is not None
                        and result.page.content_hash in seen_content_hashes
                    )
                )
                if duplicate:
                    _clear_page_artifacts(session, result.page)
                    _set_page_error(
                        result.page,
                        PageCrawlStatus.SKIPPED,
                        "DUPLICATE_CONTENT",
                        f"Duplicate final URL or content: {final_url}",
                    )
                    session.commit()
                    result.extracted = None
                elif result.page.crawl_status == PageCrawlStatus.FETCHED:
                    seen_final_urls.add(final_url)
                    if result.page.content_hash:
                        seen_content_hashes.add(result.page.content_hash)
                pages.append(result)
                visited.add(result.page.normalized_url)
                if result.extracted and result.page.depth < active_settings.crawler_max_depth:
                    for link in result.extracted.internal_links:
                        if link not in visited:
                            _add_candidate(
                                candidates, link, result.page.normalized_url, result.page.depth + 1
                            )

        failed = [page for page in pages if page.page.crawl_status == PageCrawlStatus.FAILED]
        skipped = [page for page in pages if page.page.crawl_status == PageCrawlStatus.SKIPPED]
        errors.extend(
            f"{page.page.error_code}:{page.page.normalized_url}"
            for page in failed[:20]
            if not (page.page.error_code == "HTTP_404" and page.page.discovered_from is None)
        )
        report = _finalize_company(session, company, pages, robots, started, errors)
        logger.info(
            "company=%s event=crawl_completed pages=%s strong_signals=%s status=%s",
            company.domain,
            report.pages_crawled,
            report.strong_signals,
            report.status.value,
        )
        return replace(report, pages_skipped=len(skipped))
    except Exception as exc:
        logger.exception("company=%s event=crawl_failed", company.domain)
        return _fail_company(session, company, started, [type(exc).__name__], None)
    finally:
        await fetcher.close()


async def crawl_company_ids(
    company_ids: list[int],
    *,
    force: bool = False,
    concurrency: int | None = None,
    settings: Settings | None = None,
) -> list[CrawlReport]:
    create_database()
    active_settings = settings or get_settings()
    worker_limit = min(concurrency or active_settings.crawler_global_concurrency, 20)
    company_semaphore = asyncio.Semaphore(worker_limit)
    global_semaphore = asyncio.Semaphore(active_settings.crawler_global_concurrency)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(active_settings.crawler_request_timeout),
        follow_redirects=True,
        max_redirects=active_settings.crawler_max_redirects,
        headers={"User-Agent": active_settings.crawler_user_agent},
    ) as client:

        async def run(company_id: int) -> CrawlReport:
            async with company_semaphore:
                with SessionLocal() as session:
                    return await crawl_company(
                        session,
                        company_id,
                        force=force,
                        settings=active_settings,
                        client=client,
                        global_semaphore=global_semaphore,
                    )

        return list(await asyncio.gather(*(run(company_id) for company_id in company_ids)))


def _add_candidate(
    candidates: dict[str, tuple[int, str | None, int]],
    url: str,
    discovered_from: str | None,
    depth: int,
) -> None:
    normalized = canonicalize_url(url)
    if normalized:
        priority = page_priority(normalized) + (10 if discovered_from is not None else 0)
        current = candidates.get(normalized)
        if current is None or priority > current[0]:
            candidates[normalized] = (priority, discovered_from, depth)


async def _process_page(
    session: Session,
    company: Company,
    url: str,
    depth: int,
    discovered_from: str | None,
    robots: RobotsPolicy,
    fetcher: HttpFetcher,
    settings: Settings,
) -> ProcessedPage:
    normalized = canonicalize_url(url) or url
    if not is_allowed_company_url(normalized, company.domain):
        page = _upsert_page(session, company, normalized, depth, discovered_from)
        _clear_page_artifacts(session, page)
        _set_page_error(page, PageCrawlStatus.SKIPPED, "DOMAIN_NOT_ALLOWED", None)
        session.commit()
        return ProcessedPage(page, None)
    if not robots.allowed(settings.crawler_user_agent, normalized):
        page = _upsert_page(session, company, normalized, depth, discovered_from)
        _clear_page_artifacts(session, page)
        _set_page_error(page, PageCrawlStatus.SKIPPED, "ROBOTS_DISALLOWED", None)
        session.commit()
        return ProcessedPage(page, None)

    result = await fetcher.fetch(normalized)
    logger.info(
        "company=%s url=%s event=page_fetched status=%s error=%s",
        company.domain,
        urlsplit(normalized).path or "/",
        result.status_code or 0,
        result.error_code or "none",
    )
    page = _upsert_page(session, company, normalized, depth, discovered_from)
    page.url = result.final_url
    page.status_code = result.status_code
    page.content_type = result.content_type
    page.crawled_at = datetime.now(UTC)
    if not result.ok:
        _clear_page_artifacts(session, page)
        _set_page_error(
            page, PageCrawlStatus.FAILED, result.error_code or "FETCH_FAILED", result.error_message
        )
        session.commit()
        return ProcessedPage(page, None)

    final_url = canonicalize_url(result.final_url)
    if final_url is None or not is_allowed_company_url(final_url, company.domain):
        _clear_page_artifacts(session, page)
        _set_page_error(
            page,
            PageCrawlStatus.SKIPPED,
            "REDIRECT_DOMAIN_NOT_ALLOWED",
            f"Redirected to {result.final_url}",
        )
        session.commit()
        return ProcessedPage(page, None)

    extracted = extract_html(
        result.body or "", result.final_url, company.domain, settings.crawler_text_max_chars
    )
    page.canonical_url = extracted.canonical_url
    page.page_type = classify_page(result.final_url, extracted.title or "", extracted.headings)
    page.title = extracted.title
    page.meta_description = extracted.meta_description
    page.h1 = extracted.h1
    page.headings = extracted.headings
    page.text_excerpt = extracted.visible_text
    page.content_hash = extracted.content_hash
    page.internal_links = extracted.internal_links[:200]
    page.external_links = extracted.external_links[:200]
    page.crawl_status = PageCrawlStatus.FETCHED
    page.error_code = None
    page.error_message = None
    session.flush()

    session.execute(delete(SignalEvidence).where(SignalEvidence.page_id == page.id))
    signals = detect_signals(
        extracted.visible_text, page.page_type, extracted.title, extracted.headings
    )
    for signal in signals:
        session.add(_evidence_entity(company, page, signal))
        logger.info(
            "company=%s event=signal_detected signal=%s context=%s",
            company.domain,
            signal.signal_key,
            signal.context.value,
        )
    page.signal_count = len(signals)

    session.execute(delete(PublishedEmail).where(PublishedEmail.page_id == page.id))
    for email, classification in extracted.published_emails:
        if classification in {
            EmailClassification.NAMED_BUSINESS,
            EmailClassification.GENERIC_BUSINESS,
        }:
            session.add(
                PublishedEmail(
                    company_id=company.id,
                    page_id=page.id,
                    email=email,
                    classification=classification,
                    source_url=page.normalized_url,
                )
            )
    session.commit()
    return ProcessedPage(page, extracted)


def _upsert_page(
    session: Session,
    company: Company,
    normalized_url: str,
    depth: int,
    discovered_from: str | None,
) -> CrawledPage:
    page = session.scalar(
        select(CrawledPage).where(
            CrawledPage.company_id == company.id,
            CrawledPage.normalized_url == normalized_url,
        )
    )
    if page is None:
        page = CrawledPage(
            company_id=company.id,
            url=normalized_url,
            normalized_url=normalized_url,
            page_type=classify_page(normalized_url),
            crawl_status=PageCrawlStatus.SKIPPED,
        )
        session.add(page)
    page.depth = depth
    page.discovered_from = discovered_from
    return page


def _set_page_error(
    page: CrawledPage,
    status: PageCrawlStatus,
    code: str,
    message: str | None,
) -> None:
    page.crawl_status = status
    page.error_code = code
    page.error_message = (message or "")[:500] or None
    page.signal_count = 0
    page.crawled_at = datetime.now(UTC)


def _clear_page_artifacts(session: Session, page: CrawledPage) -> None:
    """Remove derived data that is no longer supported by the latest page fetch."""
    session.flush()
    session.execute(delete(SignalEvidence).where(SignalEvidence.page_id == page.id))
    session.execute(delete(PublishedEmail).where(PublishedEmail.page_id == page.id))


def _evidence_entity(company: Company, page: CrawledPage, signal: DetectedSignal) -> SignalEvidence:
    return SignalEvidence(
        company_id=company.id,
        page_id=page.id,
        signal_type=signal.signal_type,
        signal_key=signal.signal_key,
        value=signal.value,
        evidence_text=signal.evidence_text,
        evidence_hash=signal.evidence_hash,
        source_url=page.normalized_url,
        confidence=signal.confidence,
        context=signal.context,
        detector=signal.detector,
    )


def _finalize_company(
    session: Session,
    company: Company,
    pages: list[ProcessedPage],
    robots: RobotsPolicy,
    started: float,
    errors: list[str],
) -> CrawlReport:
    evidence = list(
        session.scalars(
            select(SignalEvidence)
            .where(SignalEvidence.company_id == company.id)
            .order_by(SignalEvidence.confidence.desc())
        )
    )
    providers = sorted({item.signal_key for item in evidence if item.signal_type == "provider"})
    models = sorted({item.signal_key for item in evidence if item.signal_type == "model"})
    strong = sum(item.confidence >= 0.8 for item in evidence)
    weak = len(evidence) - strong
    fetched_pages = [
        item.page for item in pages if item.page.crawl_status == PageCrawlStatus.FETCHED
    ]
    failed_pages = [item.page for item in pages if item.page.crawl_status == PageCrawlStatus.FAILED]
    skipped_pages = [
        item.page for item in pages if item.page.crawl_status == PageCrawlStatus.SKIPPED
    ]
    signal_keys = sorted({item.signal_key for item in evidence})
    company.providers_detected = providers
    company.models_detected = models
    company.ai_signals = signal_keys
    company.ai_signal_count = len(evidence)
    company.strong_ai_signal_count = strong
    company.weak_ai_signal_count = weak
    company.openai_detected = "openai" in providers
    company.anthropic_detected = "anthropic" in providers
    company.claude_detected = "claude" in models
    company.gpt_detected = "gpt" in models
    company.gemini_detected = "gemini" in models
    company.deepseek_detected = "deepseek" in providers or "deepseek" in models
    company.openrouter_detected = "openrouter" in providers
    company.has_multiple_models = "multi_model" in signal_keys or len(models) >= 2
    company.has_model_selector_signal = "model_selector" in signal_keys
    company.has_ai_pricing_signal = "ai_pricing" in signal_keys
    company.has_ai_jobs_signal = "ai_job" in signal_keys
    company.has_ai_jobs = company.has_ai_jobs_signal
    company.llm_integration_signal = any(item.signal_type == "integration" for item in evidence)
    company.has_api_docs = any(
        page.page_type in {PageType.DOCS, PageType.API_DOCS}
        and page.crawl_status == PageCrawlStatus.FETCHED
        for page in fetched_pages
    )
    company.has_ai_docs = any(
        item.page.page_type in {PageType.DOCS, PageType.API_DOCS} and item.confidence >= 0.8
        for item in evidence
    )
    qualifying = [
        item
        for item in evidence
        if item.confidence >= 0.8
        and (
            item.signal_type in {"commercial", "integration", "model", "product", "provider"}
            or (
                item.signal_type == "concept"
                and item.signal_key in {"ai_agent", "ai_assistant", "generative_ai", "llm"}
                and item.page.page_type
                in {
                    PageType.HOME,
                    PageType.PRODUCT,
                    PageType.FEATURES,
                    PageType.INTEGRATIONS,
                    PageType.MODELS,
                }
            )
        )
    ]
    company.ai_native_candidate = len(qualifying) >= 2
    company.ai_native = company.ai_native_candidate
    duration_ms = int((time.perf_counter() - started) * 1000)
    company.crawl_duration_ms = duration_ms
    company.last_crawled_at = datetime.now(UTC)
    partial_failures = [
        page
        for page in failed_pages
        if not (page.error_code == "HTTP_404" and page.discovered_from is None)
    ]
    company.crawl_status = CrawlStatus.PARTIAL if partial_failures else CrawlStatus.CRAWLED
    company.pipeline_status = (
        PipelineStatus.CRAWL_PARTIAL if partial_failures else PipelineStatus.CRAWLED
    )
    company.error_message = "; ".join(errors[:5]) or None
    company.ai_signal_evidence = [
        {
            "signal_type": item.signal_type,
            "signal_key": item.signal_key,
            "evidence_text": item.evidence_text,
            "source_url": item.source_url,
            "confidence": item.confidence,
            "context": item.context.value,
        }
        for item in evidence[:50]
    ]
    company.crawl_summary = {
        "providers_detected": providers,
        "models_detected": models,
        "strong_signal_count": strong,
        "weak_signal_count": weak,
        "has_api_docs": company.has_api_docs,
        "has_ai_docs": company.has_ai_docs,
        "has_multi_model_signal": company.has_multiple_models,
        "has_model_selector_signal": company.has_model_selector_signal,
        "has_ai_pricing_signal": company.has_ai_pricing_signal,
        "has_ai_jobs_signal": company.has_ai_jobs_signal,
        "llm_integration_signal": company.llm_integration_signal,
        "ai_native_candidate": company.ai_native_candidate,
        "pages_crawled": len(fetched_pages),
        "pages_failed": len(failed_pages),
        "pages_skipped": len(skipped_pages),
        "crawl_duration_ms": duration_ms,
        "robots": {"status": robots.status, "url": robots.robots_url, "error": robots.error},
        "errors": errors,
    }
    session.commit()
    return CrawlReport(
        company.id,
        company.domain,
        company.crawl_status,
        len(fetched_pages),
        len(failed_pages),
        len(skipped_pages),
        strong,
        weak,
        providers,
        models,
        errors,
    )


def _fail_company(
    session: Session,
    company: Company,
    started: float,
    errors: list[str],
    robots: RobotsPolicy | None,
) -> CrawlReport:
    _clear_company_signal_summary(company)
    company.crawl_status = CrawlStatus.FAILED
    company.pipeline_status = PipelineStatus.CRAWL_FAILED
    company.last_crawled_at = datetime.now(UTC)
    company.crawl_duration_ms = int((time.perf_counter() - started) * 1000)
    company.error_message = "; ".join(errors)
    company.crawl_summary = {
        "pages_crawled": 0,
        "pages_failed": 1,
        "pages_skipped": 0,
        "strong_signal_count": 0,
        "weak_signal_count": 0,
        "errors": errors,
        "robots": (
            {"status": robots.status, "url": robots.robots_url, "error": robots.error}
            if robots
            else None
        ),
    }
    session.commit()
    return CrawlReport(
        company.id,
        company.domain,
        CrawlStatus.FAILED,
        0,
        1,
        0,
        0,
        0,
        [],
        [],
        errors,
    )


def _clear_company_signal_summary(company: Company) -> None:
    company.providers_detected = []
    company.models_detected = []
    company.ai_signals = []
    company.ai_signal_evidence = []
    company.ai_signal_count = 0
    company.strong_ai_signal_count = 0
    company.weak_ai_signal_count = 0
    company.ai_native_candidate = False
    company.ai_native = False
    company.openai_detected = False
    company.anthropic_detected = False
    company.claude_detected = False
    company.gpt_detected = False
    company.gemini_detected = False
    company.deepseek_detected = False
    company.openrouter_detected = False
    company.has_api_docs = False
    company.has_ai_docs = False
    company.has_multiple_models = False
    company.has_model_selector_signal = False
    company.has_ai_pricing_signal = False
    company.has_ai_jobs_signal = False
    company.has_ai_jobs = False
    company.llm_integration_signal = False


def _is_fresh(company: Company, settings: Settings) -> bool:
    if company.last_crawled_at is None:
        return False
    last = company.last_crawled_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return datetime.now(UTC) - last < timedelta(hours=settings.crawler_freshness_hours)
