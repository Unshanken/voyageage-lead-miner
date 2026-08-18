from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from leadminer.database import Base
from leadminer.models.enums import (
    CrawlStatus,
    EmailClassification,
    EmailStatus,
    PageCrawlStatus,
    PageType,
    PipelineStatus,
    SignalContext,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website_url: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    employee_range: Mapped[str | None] = mapped_column(String(50))

    crawl_status: Mapped[CrawlStatus] = mapped_column(
        Enum(CrawlStatus, native_enum=False), default=CrawlStatus.PENDING, index=True
    )
    pipeline_status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, native_enum=False), default=PipelineStatus.NEW, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crawl_duration_ms: Mapped[int | None] = mapped_column(Integer)

    ai_native: Mapped[bool | None] = mapped_column(Boolean)
    ai_native_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_dependency: Mapped[str | None] = mapped_column(String(20))
    openai_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    anthropic_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    claude_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    gpt_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    gemini_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    deepseek_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    openrouter_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    providers_detected: Mapped[list[str]] = mapped_column(JSON, default=list)
    models_detected: Mapped[list[str]] = mapped_column(JSON, default=list)
    has_pricing_page: Mapped[bool] = mapped_column(Boolean, default=False)
    has_paid_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    has_api_docs: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_docs: Mapped[bool] = mapped_column(Boolean, default=False)
    has_model_selector_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_pricing_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_jobs_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_integration_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_jobs: Mapped[bool] = mapped_column(Boolean, default=False)
    has_multiple_models: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    ai_signal_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    ai_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    strong_ai_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    weak_ai_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    crawl_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    voyageage_fit_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fit_reason: Mapped[str | None] = mapped_column(Text)

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    sources: Mapped[list[LeadSource]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    pages: Mapped[list[CrawledPage]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    signal_evidence: Mapped[list[SignalEvidence]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    published_emails: Mapped[list[PublishedEmail]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class LeadSource(TimestampMixin, Base):
    __tablename__ = "lead_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(100), default="manual")
    source_url: Mapped[str | None] = mapped_column(String(2048))
    external_id: Mapped[str | None] = mapped_column(String(255))

    company: Mapped[Company] = relationship(back_populates="sources")


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    seniority: Mapped[str | None] = mapped_column(String(100))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    github_url: Mapped[str | None] = mapped_column(String(2048))
    twitter_url: Mapped[str | None] = mapped_column(String(2048))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    email_domain: Mapped[str | None] = mapped_column(String(255))
    email_source: Mapped[str | None] = mapped_column(String(100))
    email_confidence: Mapped[float | None] = mapped_column(Float)
    email_status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, native_enum=False), default=EmailStatus.UNKNOWN
    )
    is_business_email: Mapped[bool] = mapped_column(Boolean, default=True)
    is_generic_email: Mapped[bool] = mapped_column(Boolean, default=False)
    personalization_opener: Mapped[str | None] = mapped_column(Text)
    personalization_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="contacts")


class Suppression(TimestampMixin, Base):
    __tablename__ = "suppressions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(500))


class CrawledPage(TimestampMixin, Base):
    __tablename__ = "crawled_pages"
    __table_args__ = (UniqueConstraint("company_id", "normalized_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str] = mapped_column(String(2048), index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    page_type: Mapped[PageType] = mapped_column(Enum(PageType, native_enum=False))
    status_code: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    meta_description: Mapped[str | None] = mapped_column(Text)
    h1: Mapped[str | None] = mapped_column(String(500))
    headings: Mapped[list[str]] = mapped_column(JSON, default=list)
    text_excerpt: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    internal_links: Mapped[list[str]] = mapped_column(JSON, default=list)
    external_links: Mapped[list[str]] = mapped_column(JSON, default=list)
    crawl_status: Mapped[PageCrawlStatus] = mapped_column(
        Enum(PageCrawlStatus, native_enum=False), index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    discovered_from: Mapped[str | None] = mapped_column(String(2048))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="pages")
    evidence: Mapped[list[SignalEvidence]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class SignalEvidence(TimestampMixin, Base):
    __tablename__ = "signal_evidence"
    __table_args__ = (
        UniqueConstraint("company_id", "page_id", "signal_type", "signal_key", "evidence_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    page_id: Mapped[int] = mapped_column(ForeignKey("crawled_pages.id", ondelete="CASCADE"))
    signal_type: Mapped[str] = mapped_column(String(50), index=True)
    signal_key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[str] = mapped_column(String(255), default="true")
    evidence_text: Mapped[str] = mapped_column(String(500))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(2048))
    confidence: Mapped[float] = mapped_column(Float)
    context: Mapped[SignalContext] = mapped_column(Enum(SignalContext, native_enum=False))
    detector: Mapped[str] = mapped_column(String(100), default="deterministic-v1")

    company: Mapped[Company] = relationship(back_populates="signal_evidence")
    page: Mapped[CrawledPage] = relationship(back_populates="evidence")


class PublishedEmail(TimestampMixin, Base):
    __tablename__ = "published_emails"
    __table_args__ = (UniqueConstraint("company_id", "email", "source_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    page_id: Mapped[int | None] = mapped_column(ForeignKey("crawled_pages.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320), index=True)
    classification: Mapped[EmailClassification] = mapped_column(
        Enum(EmailClassification, native_enum=False)
    )
    source_url: Mapped[str] = mapped_column(String(2048))

    company: Mapped[Company] = relationship(back_populates="published_emails")
