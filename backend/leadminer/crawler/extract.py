import hashlib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from leadminer.crawler.urls import canonicalize_url, is_allowed_company_url
from leadminer.models import EmailClassification

_EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_GENERIC_LOCAL_PARTS = {
    "admin",
    "contact",
    "hello",
    "help",
    "info",
    "office",
    "sales",
    "support",
    "team",
}
_FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
}


@dataclass(slots=True)
class ExtractedPage:
    canonical_url: str | None
    title: str | None
    meta_description: str | None
    h1: str | None
    headings: list[str]
    visible_text: str
    content_hash: str
    internal_links: list[str]
    external_links: list[str]
    published_emails: list[tuple[str, EmailClassification]]


def extract_html(html: str, url: str, company_domain: str, text_limit: int) -> ExtractedPage:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else None
    description_node = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = (
        _clean_text(str(description_node.get("content", ""))) if description_node else None
    )
    canonical_node = soup.find("link", attrs={"rel": lambda value: value and "canonical" in value})
    canonical_url = (
        canonicalize_url(str(canonical_node.get("href", "")), url) if canonical_node else None
    )

    internal: set[str] = set()
    external: set[str] = set()
    email_values: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", "")).strip()
        if href.lower().startswith("mailto:"):
            email_values.add(href[7:].split("?", 1)[0].lower())
            continue
        normalized = canonicalize_url(href, url)
        if not normalized:
            continue
        if is_allowed_company_url(normalized, company_domain):
            internal.add(normalized)
        else:
            external.add(normalized)

    for node in soup.select("script, style, noscript, svg, template, iframe, nav, footer, aside"):
        node.decompose()
    for node in soup.find_all(attrs={"id": re.compile("cookie|consent", re.I)}):
        node.decompose()
    for node in soup.find_all(attrs={"class": re.compile("cookie|consent", re.I)}):
        node.decompose()

    headings = [
        text
        for node in soup.find_all(["h1", "h2", "h3"])
        if (text := _clean_text(node.get_text(" ", strip=True)))
    ][:30]
    h1_node = soup.find("h1")
    h1 = _clean_text(h1_node.get_text(" ", strip=True)) if h1_node else None
    visible_text = _clean_text(soup.get_text(" ", strip=True))
    email_values.update(match.group(1).lower() for match in _EMAIL_RE.finditer(visible_text))
    excerpt = visible_text[:text_limit]
    published = sorted((email, classify_email(email, company_domain)) for email in email_values)
    return ExtractedPage(
        canonical_url=canonical_url,
        title=title,
        meta_description=meta_description,
        h1=h1,
        headings=headings,
        visible_text=excerpt,
        content_hash=hashlib.sha256(visible_text.encode("utf-8")).hexdigest(),
        internal_links=sorted(internal),
        external_links=sorted(external),
        published_emails=published,
    )


def classify_email(email: str, company_domain: str) -> EmailClassification:
    local, _, domain = email.lower().partition("@")
    if not local or not domain:
        return EmailClassification.UNKNOWN
    if domain in _FREE_EMAIL_DOMAINS:
        return EmailClassification.PERSONAL_FREE
    company_root = company_domain.lower().removeprefix("www.")
    if domain == company_root or domain.endswith(f".{company_root}"):
        if local in _GENERIC_LOCAL_PARTS:
            return EmailClassification.GENERIC_BUSINESS
        return EmailClassification.NAMED_BUSINESS
    return EmailClassification.UNKNOWN


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
