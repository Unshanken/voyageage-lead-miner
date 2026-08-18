import csv
import io
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from leadminer.models import Company, LeadSource
from leadminer.services.domains import InvalidDomainError, normalize_website


@dataclass(slots=True)
class CompanyInput:
    website: str | None = None
    domain: str | None = None
    company_name: str | None = None
    source: str = "manual"
    source_url: str | None = None


@dataclass(slots=True)
class ImportErrorItem:
    row: int
    value: str
    message: str


@dataclass(slots=True)
class ImportResult:
    created: int = 0
    existing: int = 0
    sources_added: int = 0
    errors: list[ImportErrorItem] = field(default_factory=list)


def import_companies(session: Session, items: list[CompanyInput]) -> ImportResult:
    result = ImportResult()
    for row_number, item in enumerate(items, start=1):
        raw_website = item.website or item.domain or ""
        try:
            normalized = normalize_website(raw_website)
        except InvalidDomainError as exc:
            result.errors.append(ImportErrorItem(row_number, raw_website, str(exc)))
            continue

        company = session.scalar(select(Company).where(Company.domain == normalized.domain))
        if company:
            result.existing += 1
            if not company.company_name and item.company_name:
                company.company_name = item.company_name.strip() or None
        else:
            company = Company(
                company_name=(item.company_name or "").strip() or None,
                domain=normalized.domain,
                website_url=normalized.website_url,
            )
            session.add(company)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                result.existing += 1
                company = session.scalar(select(Company).where(Company.domain == normalized.domain))
                if company is None:
                    raise
            else:
                result.created += 1

        if company and _add_source(session, company, item.source, item.source_url):
            result.sources_added += 1

    session.commit()
    return result


def _add_source(
    session: Session, company: Company, source: str | None, source_url: str | None
) -> bool:
    source_name = (source or "manual").strip() or "manual"
    existing = session.scalar(
        select(LeadSource).where(
            LeadSource.company_id == company.id,
            LeadSource.source == source_name,
            LeadSource.source_url == source_url,
        )
    )
    if existing:
        return False
    session.add(LeadSource(company=company, source=source_name, source_url=source_url))
    return True


def parse_company_csv(content: bytes) -> list[CompanyInput]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV is empty or missing a header row")
    allowed = {"company_name", "website", "website_url", "domain", "source", "source_url"}
    unknown = set(reader.fieldnames) - allowed
    if unknown:
        raise ValueError(f"Unsupported CSV columns: {', '.join(sorted(unknown))}")
    if not ({"website", "website_url", "domain"} & set(reader.fieldnames)):
        raise ValueError("CSV needs a website, website_url, or domain column")

    rows: list[CompanyInput] = []
    for row in reader:
        rows.append(
            CompanyInput(
                company_name=row.get("company_name") or None,
                website=row.get("website") or row.get("website_url") or None,
                domain=row.get("domain") or None,
                source=row.get("source") or "csv",
                source_url=row.get("source_url") or None,
            )
        )
    return rows
