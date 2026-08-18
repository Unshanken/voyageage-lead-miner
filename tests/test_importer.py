from leadminer.models import Company, LeadSource, Suppression
from leadminer.services.importer import CompanyInput, import_companies, parse_company_csv
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_import_deduplicates_domain_and_preserves_provenance(session: Session) -> None:
    result = import_companies(
        session,
        [
            CompanyInput(website="https://www.example.com/", source="csv"),
            CompanyInput(
                domain="example.com",
                company_name="Example AI",
                source="manual",
                source_url="list-2",
            ),
        ],
    )

    assert result.created == 1
    assert result.existing == 1
    assert result.sources_added == 2
    assert session.scalar(select(func.count()).select_from(Company)) == 1
    assert session.scalar(select(func.count()).select_from(LeadSource)) == 2
    company = session.scalar(select(Company))
    assert company is not None
    assert company.company_name == "Example AI"


def test_reimport_same_provenance_is_idempotent(session: Session) -> None:
    item = CompanyInput(website="example.com", source="csv", source_url="batch-1")
    first = import_companies(session, [item])
    second = import_companies(session, [item])

    assert first.created == 1
    assert second.existing == 1
    assert second.sources_added == 0


def test_csv_import_accepts_supported_columns() -> None:
    rows = parse_company_csv(
        b"company_name,website,source,source_url\nExample AI,example.com,directory,https://source.test\n"
    )
    assert len(rows) == 1
    assert rows[0].company_name == "Example AI"
    assert rows[0].website == "example.com"
    assert rows[0].source == "directory"


def test_csv_import_rejects_unknown_columns() -> None:
    try:
        parse_company_csv(b"website,secret\nexample.com,nope\n")
    except ValueError as error:
        assert "Unsupported CSV columns" in str(error)
    else:
        raise AssertionError("Unknown columns must be rejected")


def test_suppression_can_store_domain_or_email(session: Session) -> None:
    session.add_all(
        [
            Suppression(domain="example.com", reason="unsubscribed domain"),
            Suppression(email="founder@another.test", reason="unsubscribed contact"),
        ]
    )
    session.commit()
    suppressions = list(session.scalars(select(Suppression).order_by(Suppression.id)))
    assert suppressions[0].domain == "example.com"
    assert suppressions[1].email == "founder@another.test"
