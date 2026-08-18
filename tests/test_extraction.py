from pathlib import Path

from leadminer.crawler.extract import extract_html
from leadminer.models import EmailClassification

FIXTURES = Path(__file__).parent / "fixtures" / "pages"


def test_html_extraction_and_business_email_classification() -> None:
    extracted = extract_html(
        (FIXTURES / "non_ai.html").read_text(encoding="utf-8"),
        "https://acme.test/",
        "acme.test",
        12_000,
    )
    assert extracted.title == "Acme Scheduling"
    assert extracted.h1 == "Intelligent team scheduling"
    assert ("hello@acme.test", EmailClassification.GENERIC_BUSINESS) in extracted.published_emails


def test_navigation_text_removed_but_links_preserved() -> None:
    extracted = extract_html(
        "<html><body><nav>Repeated nav <a href='/docs'>Docs</a></nav>"
        "<main>Product body</main></body></html>",
        "https://example.test/",
        "example.test",
        12_000,
    )
    assert "Repeated nav" not in extracted.visible_text
    assert "https://example.test/docs" in extracted.internal_links
