from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from leadminer.api.schemas import (
    BatchCompanyCreate,
    CompanyCreate,
    CompanyRead,
    CrawlBatchRequest,
    CrawledPageRead,
    CrawlQueuedRead,
    CrawlStatusRead,
    ImportResultRead,
    OverviewRead,
    PublishedEmailRead,
    SignalEvidenceRead,
)
from leadminer.crawler.service import crawl_company_ids
from leadminer.database import get_session
from leadminer.models import (
    Company,
    Contact,
    CrawledPage,
    EmailStatus,
    PipelineStatus,
    PublishedEmail,
    SignalEvidence,
)
from leadminer.services.importer import CompanyInput, import_companies, parse_company_csv

router = APIRouter(prefix="/api")
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/overview", response_model=OverviewRead)
def overview(session: SessionDep) -> OverviewRead:
    companies = session.scalar(select(func.count()).select_from(Company)) or 0
    analyzed = (
        session.scalar(
            select(func.count()).select_from(Company).where(Company.last_analyzed_at.is_not(None))
        )
        or 0
    )
    high_fit = (
        session.scalar(
            select(func.count()).select_from(Company).where(Company.voyageage_fit_score >= 75)
        )
        or 0
    )
    verified = (
        session.scalar(
            select(func.count())
            .select_from(Contact)
            .where(Contact.email_status == EmailStatus.VALID)
        )
        or 0
    )
    export_ready = (
        session.scalar(
            select(func.count())
            .select_from(Company)
            .join(Contact)
            .where(
                Company.voyageage_fit_score >= 75,
                Contact.email_status == EmailStatus.VALID,
                Contact.is_business_email.is_(True),
            )
        )
        or 0
    )
    return OverviewRead(
        companies_discovered=companies,
        companies_analyzed=analyzed,
        high_fit_leads=high_fit,
        verified_contacts=verified,
        export_ready=export_ready,
    )


@router.get("/companies", response_model=list[CompanyRead])
def list_companies(
    session: SessionDep,
    search: str | None = None,
    score_min: int = Query(default=0, ge=0, le=100),
    pipeline_status: PipelineStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Company]:
    query = (
        select(Company)
        .options(selectinload(Company.contacts), selectinload(Company.sources))
        .where(Company.voyageage_fit_score >= score_min)
        .order_by(Company.voyageage_fit_score.desc(), Company.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Company.company_name.ilike(term), Company.domain.ilike(term)))
    if pipeline_status:
        query = query.where(Company.pipeline_status == pipeline_status)
    return list(session.scalars(query).unique())


@router.get("/companies/{company_id:int}", response_model=CompanyRead)
def get_company(company_id: int, session: SessionDep) -> Company:
    company = session.scalar(
        select(Company)
        .options(selectinload(Company.contacts), selectinload(Company.sources))
        .where(Company.id == company_id)
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post(
    "/companies/{company_id:int}/crawl",
    response_model=CrawlQueuedRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_company_crawl(
    company_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    force: bool = False,
) -> CrawlQueuedRead:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    background_tasks.add_task(crawl_company_ids, [company_id], force=force, concurrency=1)
    return CrawlQueuedRead(company_ids=[company_id], queued=1, force=force)


@router.post(
    "/companies/crawl-batch",
    response_model=CrawlQueuedRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_company_batch_crawl(
    payload: CrawlBatchRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> CrawlQueuedRead:
    if payload.company_ids:
        company_ids = list(
            session.scalars(
                select(Company.id)
                .where(Company.id.in_(payload.company_ids))
                .order_by(Company.created_at)
                .limit(payload.limit)
            )
        )
    else:
        company_ids = list(
            session.scalars(
                select(Company.id)
                .order_by(Company.last_crawled_at.asc().nulls_first(), Company.created_at)
                .limit(payload.limit)
            )
        )
    background_tasks.add_task(
        crawl_company_ids,
        company_ids,
        force=payload.force,
        concurrency=payload.concurrency,
    )
    return CrawlQueuedRead(company_ids=company_ids, queued=len(company_ids), force=payload.force)


@router.get("/companies/{company_id:int}/crawl", response_model=CrawlStatusRead)
def get_crawl_status(company_id: int, session: SessionDep) -> CrawlStatusRead:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return CrawlStatusRead(
        company_id=company.id,
        domain=company.domain,
        crawl_status=company.crawl_status,
        pipeline_status=company.pipeline_status,
        last_crawled_at=company.last_crawled_at,
        crawl_duration_ms=company.crawl_duration_ms,
        summary=company.crawl_summary,
        error_message=company.error_message,
    )


@router.get("/companies/{company_id:int}/pages", response_model=list[CrawledPageRead])
def get_crawled_pages(company_id: int, session: SessionDep) -> list[CrawledPage]:
    _require_company(session, company_id)
    return list(
        session.scalars(
            select(CrawledPage)
            .where(CrawledPage.company_id == company_id)
            .order_by(CrawledPage.depth, CrawledPage.normalized_url)
        )
    )


@router.get("/companies/{company_id:int}/signals", response_model=list[SignalEvidenceRead])
def get_signals(company_id: int, session: SessionDep) -> list[SignalEvidence]:
    _require_company(session, company_id)
    return list(
        session.scalars(
            select(SignalEvidence)
            .where(SignalEvidence.company_id == company_id)
            .order_by(SignalEvidence.confidence.desc(), SignalEvidence.signal_key)
        )
    )


@router.get("/companies/{company_id:int}/published-emails", response_model=list[PublishedEmailRead])
def get_published_emails(company_id: int, session: SessionDep) -> list[PublishedEmail]:
    _require_company(session, company_id)
    return list(
        session.scalars(
            select(PublishedEmail)
            .where(PublishedEmail.company_id == company_id)
            .order_by(PublishedEmail.email)
        )
    )


@router.post("/companies", response_model=ImportResultRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, session: SessionDep):
    return import_companies(
        session,
        [
            CompanyInput(
                website=payload.website,
                company_name=payload.company_name,
                source=payload.source,
                source_url=payload.source_url,
            )
        ],
    )


@router.post(
    "/companies/batch", response_model=ImportResultRead, status_code=status.HTTP_201_CREATED
)
def create_company_batch(payload: BatchCompanyCreate, session: SessionDep):
    items = [CompanyInput(website=value, source=payload.source) for value in payload.websites]
    return import_companies(session, items)


@router.post(
    "/companies/import-csv", response_model=ImportResultRead, status_code=status.HTTP_201_CREATED
)
async def import_company_csv(
    session: SessionDep, file: Annotated[UploadFile, File(description="UTF-8 company CSV")]
):
    if file.size is not None and file.size > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 5 MB limit")
    content = await file.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 5 MB limit")
    try:
        items = parse_company_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return import_companies(session, items)


@router.delete("/companies/{company_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, session: SessionDep) -> None:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    session.delete(company)
    session.commit()


def _require_company(session: Session, company_id: int) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
