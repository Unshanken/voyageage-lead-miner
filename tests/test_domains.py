import pytest
from leadminer.services.domains import InvalidDomainError, normalize_domain, normalize_website


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.example.com/", "example.com"),
        ("www.example.com", "example.com"),
        ("example.com", "example.com"),
        ("HTTP://EXAMPLE.COM/pricing?ref=source", "example.com"),
        ("https://sub.example.com:443/path", "sub.example.com"),
    ],
)
def test_domain_normalization(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected
    assert normalize_website(raw).website_url == f"https://{expected}"


@pytest.mark.parametrize("raw", ["", "localhost", "ftp://example.com", "127.0.0.1"])
def test_domain_normalization_rejects_unsafe_inputs(raw: str) -> None:
    with pytest.raises(InvalidDomainError):
        normalize_domain(raw)
