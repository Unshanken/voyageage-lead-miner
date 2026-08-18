import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


class InvalidDomainError(ValueError):
    """Raised when input cannot be converted to a safe HTTP(S) domain."""


@dataclass(frozen=True, slots=True)
class NormalizedWebsite:
    domain: str
    website_url: str


_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domain(value: str) -> str:
    return normalize_website(value).domain


def normalize_website(value: str) -> NormalizedWebsite:
    raw = value.strip()
    if not raw:
        raise InvalidDomainError("Website or domain is required")

    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidDomainError("Only HTTP and HTTPS websites are supported")
    if parsed.username or parsed.password:
        raise InvalidDomainError("Credentials are not allowed in website URLs")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidDomainError(f"Could not find a domain in {value!r}")

    hostname = hostname.rstrip(".").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidDomainError("Domain contains invalid characters") from exc

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        labels = hostname.split(".")
        if len(labels) < 2 or any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
            raise InvalidDomainError(f"Invalid public domain: {hostname}") from None
    else:
        raise InvalidDomainError("IP addresses are not accepted as company domains")

    return NormalizedWebsite(domain=hostname, website_url=f"https://{hostname}")
