from fastapi.testclient import TestClient
from leadminer.api import routes
from leadminer.database import get_session
from leadminer.main import create_app
from leadminer.models import (
    Company,
    CrawledPage,
    PageCrawlStatus,
    PageType,
    SignalContext,
    SignalEvidence,
)
from pytest import MonkeyPatch
from sqlalchemy.orm import Session


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_phase2_detail_endpoints(session: Session) -> None:
    company = Company(domain="api.test", website_url="https://api.test")
    session.add(company)
    session.flush()
    page = CrawledPage(
        company_id=company.id,
        url="https://api.test/docs",
        normalized_url="https://api.test/docs",
        page_type=PageType.DOCS,
        crawl_status=PageCrawlStatus.FETCHED,
        status_code=200,
        signal_count=1,
    )
    session.add(page)
    session.flush()
    session.add(
        SignalEvidence(
            company_id=company.id,
            page_id=page.id,
            signal_type="provider",
            signal_key="openai",
            value="true",
            evidence_text="Set OPENAI_API_KEY",
            evidence_hash="fixture",
            source_url=page.normalized_url,
            confidence=0.98,
            context=SignalContext.EXPLICIT_INTEGRATION,
        )
    )
    session.commit()

    application = create_app()

    def override_session():
        yield session

    application.dependency_overrides[get_session] = override_session
    client = TestClient(application)
    assert client.get(f"/api/companies/{company.id}/crawl").status_code == 200
    pages = client.get(f"/api/companies/{company.id}/pages")
    signals = client.get(f"/api/companies/{company.id}/signals")
    assert pages.status_code == 200
    assert pages.json()[0]["page_type"] == "DOCS"
    assert signals.status_code == 200
    assert signals.json()[0]["signal_key"] == "openai"


def test_batch_crawl_static_route_queues_companies(
    session: Session, monkeypatch: MonkeyPatch
) -> None:
    companies = [
        Company(domain="one.test", website_url="https://one.test"),
        Company(domain="two.test", website_url="https://two.test"),
    ]
    session.add_all(companies)
    session.commit()
    calls: list[tuple[list[int], bool, int | None]] = []

    async def fake_crawl(
        company_ids: list[int], *, force: bool = False, concurrency: int | None = None
    ) -> list[object]:
        calls.append((company_ids, force, concurrency))
        return []

    monkeypatch.setattr(routes, "crawl_company_ids", fake_crawl)
    application = create_app()

    def override_session():
        yield session

    application.dependency_overrides[get_session] = override_session
    response = TestClient(application).post(
        "/api/companies/crawl-batch",
        json={
            "company_ids": [company.id for company in companies],
            "limit": 20,
            "force": True,
            "concurrency": 2,
        },
    )
    assert response.status_code == 202
    assert response.json()["queued"] == 2
    assert calls == [([company.id for company in companies], True, 2)]
