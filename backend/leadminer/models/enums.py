from enum import StrEnum


class PipelineStatus(StrEnum):
    NEW = "NEW"
    CRAWLING = "CRAWLING"
    CRAWLED = "CRAWLED"
    CRAWL_PARTIAL = "CRAWL_PARTIAL"
    CRAWL_FAILED = "CRAWL_FAILED"
    ANALYZED = "ANALYZED"
    CONTACT_FOUND = "CONTACT_FOUND"
    EMAIL_FOUND = "EMAIL_FOUND"
    VERIFIED = "VERIFIED"
    PERSONALIZED = "PERSONALIZED"
    EXPORT_READY = "EXPORT_READY"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class EmailStatus(StrEnum):
    UNKNOWN = "unknown"
    VALID = "valid"
    RISKY = "risky"
    INVALID = "invalid"
    ACCEPT_ALL = "accept_all"


class CrawlStatus(StrEnum):
    PENDING = "PENDING"
    CRAWLING = "CRAWLING"
    CRAWLED = "CRAWLED"
    PARTIAL = "CRAWL_PARTIAL"
    FAILED = "CRAWL_FAILED"
    FRESH = "FRESH"


class PageCrawlStatus(StrEnum):
    FETCHED = "FETCHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PageType(StrEnum):
    HOME = "HOME"
    PRICING = "PRICING"
    PRODUCT = "PRODUCT"
    FEATURES = "FEATURES"
    DOCS = "DOCS"
    API_DOCS = "API_DOCS"
    INTEGRATIONS = "INTEGRATIONS"
    MODELS = "MODELS"
    ABOUT = "ABOUT"
    TEAM = "TEAM"
    CAREERS = "CAREERS"
    BLOG = "BLOG"
    OTHER = "OTHER"


class SignalContext(StrEnum):
    EXPLICIT_INTEGRATION = "EXPLICIT_INTEGRATION"
    PRODUCT_FEATURE = "PRODUCT_FEATURE"
    TECHNICAL_DOCS = "TECHNICAL_DOCS"
    PRICING_FEATURE = "PRICING_FEATURE"
    CAREERS_SIGNAL = "CAREERS_SIGNAL"
    EDITORIAL_MENTION = "EDITORIAL_MENTION"
    GENERIC_MENTION = "GENERIC_MENTION"


class EmailClassification(StrEnum):
    NAMED_BUSINESS = "named_business_email"
    GENERIC_BUSINESS = "generic_business_email"
    PERSONAL_FREE = "personal_free_email"
    UNKNOWN = "unknown"
