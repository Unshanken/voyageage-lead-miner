import pytest
from leadminer.crawler.urls import (
    canonicalize_url,
    classify_page,
    is_allowed_company_url,
    is_blocked_path,
    page_priority,
)
from leadminer.models import PageType


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.example.com/docs/?x=1#setup", "https://example.com/docs"),
        ("https://EXAMPLE.com:443/", "https://example.com/"),
    ],
)
def test_url_canonicalization(url: str, expected: str) -> None:
    assert canonicalize_url(url) == expected


def test_conservative_subdomain_policy() -> None:
    assert is_allowed_company_url("https://docs.example.com/start", "example.com")
    assert is_allowed_company_url("https://api.example.com/reference", "example.com")
    assert not is_allowed_company_url("https://customer1.example.com/app", "example.com")
    assert not is_allowed_company_url("https://example.net/docs", "example.com")


def test_blocked_paths_and_priorities() -> None:
    assert is_blocked_path("https://example.com/login")
    assert is_blocked_path("https://example.com/legal/privacy")
    assert page_priority("https://example.com/docs") > page_priority("https://example.com/blog")


def test_page_classification() -> None:
    assert classify_page("https://example.com/pricing") == PageType.PRICING
    assert (
        classify_page("https://docs.example.com/api/reference", "API Reference")
        == PageType.API_DOCS
    )
    assert classify_page("https://example.com/blog/news") == PageType.BLOG
