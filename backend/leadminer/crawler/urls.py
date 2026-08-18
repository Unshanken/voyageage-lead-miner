import posixpath
from urllib.parse import urljoin, urlsplit, urlunsplit

import tldextract

from leadminer.models import PageType

_extract_tld = tldextract.TLDExtract(suffix_list_urls=())

HIGH_VALUE_PATHS = (
    "/docs",
    "/documentation",
    "/developers",
    "/api",
    "/models",
    "/integrations",
    "/pricing",
    "/features",
    "/product",
    "/careers",
    "/jobs",
    "/about",
    "/about-us",
    "/team",
    "/blog",
)

_BLOCKED_SEGMENTS = {
    "account",
    "auth",
    "calendar",
    "cart",
    "checkout",
    "cookie",
    "dashboard",
    "legal",
    "login",
    "logout",
    "privacy",
    "search",
    "sign-in",
    "signin",
    "signup",
    "terms",
}
_DOC_SUBDOMAINS = {"api", "developer", "developers", "docs", "documentation"}


def registrable_domain(hostname: str) -> str:
    extracted = _extract_tld(hostname.lower().strip("."))
    return extracted.top_domain_under_public_suffix or hostname.lower().strip(".")


def canonicalize_url(value: str, base_url: str | None = None) -> str | None:
    absolute = urljoin(base_url or "", value.strip())
    parsed = urlsplit(absolute)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    netloc = (
        host if port is None or (parsed.scheme == "https" and port == 443) else f"{host}:{port}"
    )
    raw_path = parsed.path or "/"
    normalized_path = posixpath.normpath(raw_path)
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    if normalized_path != "/":
        normalized_path = normalized_path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, normalized_path, "", ""))


def is_blocked_path(url: str) -> bool:
    segments = {segment.lower() for segment in urlsplit(url).path.split("/") if segment}
    return bool(segments & _BLOCKED_SEGMENTS)


def is_allowed_company_url(url: str, company_domain: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    company_host = company_domain.lower().removeprefix("www.")
    if host == company_host:
        return not is_blocked_path(url)
    if registrable_domain(host) != registrable_domain(company_host):
        return False
    prefix = host.removesuffix(f".{registrable_domain(host)}").strip(".")
    return prefix in _DOC_SUBDOMAINS and not is_blocked_path(url)


def page_priority(url: str, anchor_text: str = "") -> int:
    path = urlsplit(url).path.lower().rstrip("/") or "/"
    text = anchor_text.lower()
    if path == "/":
        return 100
    priorities = {
        "docs": 95,
        "documentation": 95,
        "api": 95,
        "developer": 94,
        "developers": 94,
        "models": 93,
        "model": 92,
        "integrations": 90,
        "pricing": 88,
        "features": 86,
        "product": 85,
        "ai": 84,
        "careers": 70,
        "jobs": 70,
        "about": 65,
        "team": 64,
        "blog": 35,
    }
    score = 10
    for keyword, priority in priorities.items():
        if keyword in path.split("/") or keyword in text:
            score = max(score, priority)
    score -= max(0, len([part for part in path.split("/") if part]) - 2) * 3
    return score


def classify_page(url: str, title: str = "", headings: list[str] | None = None) -> PageType:
    path = urlsplit(url).path.lower().strip("/")
    words = f"{path} {title} {' '.join(headings or [])}".lower()
    if not path:
        return PageType.HOME
    rules = (
        (PageType.PRICING, ("pricing", "plans")),
        (PageType.API_DOCS, ("api reference", "api docs", "/api")),
        (PageType.DOCS, ("docs", "documentation", "developer")),
        (PageType.INTEGRATIONS, ("integration", "providers")),
        (PageType.MODELS, ("models", "model catalog", "model library")),
        (PageType.FEATURES, ("features",)),
        (PageType.PRODUCT, ("product", "platform")),
        (PageType.CAREERS, ("careers", "jobs", "open positions")),
        (PageType.TEAM, ("team", "leadership")),
        (PageType.ABOUT, ("about", "company")),
        (PageType.BLOG, ("blog", "news", "article")),
    )
    path_marker = f"/{path}"
    haystack = f"{path_marker} {words}"
    for page_type, needles in rules:
        if any(needle in haystack for needle in needles):
            return page_type
    return PageType.OTHER
