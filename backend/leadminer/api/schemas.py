from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from leadminer.models.enums import (
    CrawlStatus,
    EmailClassification,
    EmailStatus,
    PageCrawlStatus,
    PageType,
    PipelineStatus,
    SignalContext,
)


class CompanyCreate(BaseModel):
    website: str
    company_name: str | None = None
    source: str = "manual"
    source_url: str | None = None


class BatchCompanyCreate(BaseModel):
    websites: list[str] = Field(min_length=1, max_length=500)
    source: str = "manual"


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    source_url: str | None


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None
    title: str | None
    email: str | None
    email_status: EmailStatus


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str | None
    domain: str
    website_url: str
    description: str | None
    ai_native: bool | None
    ai_native_candidate: bool
    llm_dependency: str | None
    providers_detected: list[str]
    models_detected: list[str]
    ai_signals: list[str]
    ai_signal_count: int
    strong_ai_signal_count: int
    weak_ai_signal_count: int
    has_api_docs: bool
    has_ai_docs: bool
    has_multiple_models: bool
    has_ai_pricing_signal: bool
    has_ai_jobs_signal: bool
    llm_integration_signal: bool
    crawl_status: CrawlStatus
    last_crawled_at: datetime | None
    crawl_duration_ms: int | None
    crawl_summary: dict
    voyageage_fit_score: int
    fit_reason: str | None
    pipeline_status: PipelineStatus
    error_message: str | None
    created_at: datetime
    contacts: list[ContactRead]
    sources: list[SourceRead]


class ImportErrorRead(BaseModel):
    row: int
    value: str
    message: str


class ImportResultRead(BaseModel):
    created: int
    existing: int
    sources_added: int
    errors: list[ImportErrorRead]


class OverviewRead(BaseModel):
    companies_discovered: int
    companies_analyzed: int
    high_fit_leads: int
    verified_contacts: int
    export_ready: int


class CrawlBatchRequest(BaseModel):
    company_ids: list[int] | None = Field(default=None, max_length=500)
    limit: int = Field(default=20, ge=1, le=500)
    force: bool = False
    concurrency: int | None = Field(default=None, ge=1, le=20)


class CrawlQueuedRead(BaseModel):
    company_ids: list[int]
    queued: int
    force: bool


class CrawlStatusRead(BaseModel):
    company_id: int
    domain: str
    crawl_status: CrawlStatus
    pipeline_status: PipelineStatus
    last_crawled_at: datetime | None
    crawl_duration_ms: int | None
    summary: dict
    error_message: str | None


class CrawledPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    normalized_url: str
    canonical_url: str | None
    page_type: PageType
    status_code: int | None
    content_type: str | None
    title: str | None
    meta_description: str | None
    h1: str | None
    crawl_status: PageCrawlStatus
    error_code: str | None
    error_message: str | None
    discovered_from: str | None
    depth: int
    signal_count: int
    crawled_at: datetime | None


class SignalEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    signal_type: str
    signal_key: str
    value: str
    evidence_text: str
    source_url: str
    confidence: float
    context: SignalContext
    detector: str


class PublishedEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int | None
    email: str
    classification: EmailClassification
    source_url: str
