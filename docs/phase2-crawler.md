# Phase 2 crawler and signal contract

## Safety and crawl policy

- HTTP(S) HTML only; no authenticated pages, CAPTCHA handling, browser spoofing, or access-control bypass.
- Fetches `robots.txt` once per company crawl. Explicit disallows are persisted as skipped pages. An unavailable robots file is logged and treated as allow-by-default.
- Starts with the homepage, prioritizes discovered internal links, then cautiously probes a bounded list of common high-value routes.
- Drops query strings and fragments, canonicalizes `www`, blocks account/login/checkout/legal/search paths, and never follows arbitrary external domains.
- Obvious `docs`, `documentation`, `developer(s)`, and `api` subdomains are allowed only when they share the registrable company domain.
- Default limits: 12 pages, depth 2, 15-second timeout, 2 MB, 2 retries, two requests per domain, eight globally, 0.5-second delay.
- Only transient timeout/transport/429/5xx failures are retried. `Retry-After` is honored up to the configured cap.

## Persistence

`CrawledPage` stores page metadata, bounded text, content hash, links, status, discovery source, depth, and errors. Raw HTML is not stored.

`SignalEvidence` stores one strongest instance per signal key/type/page, with a concise snippet, source URL, confidence, context, and detector version. Forced recrawls replace evidence for updated pages.

`PublishedEmail` stores only explicitly published named or generic company-domain addresses. Free-mail and unknown-domain addresses may be classified during extraction but are not persisted as business leads.

## Deterministic contexts

- `EXPLICIT_INTEGRATION`: SDK imports, API hosts, or provider API-key variables.
- `TECHNICAL_DOCS`: provider/model/concept evidence on docs and API pages.
- `PRODUCT_FEATURE`: product/home/features/integrations/model pages, strengthened by integration language.
- `PRICING_FEATURE`: AI/model/credit evidence on pricing pages.
- `CAREERS_SIGNAL`: actual AI/ML/LLM-related role titles on careers pages.
- `EDITORIAL_MENTION`: provider/model mentions on blog pages; deliberately weak.
- `GENERIC_MENTION`: unqualified evidence elsewhere; deliberately weak.

Confidence `>= 0.8` is treated as strong. This threshold is an evidence quality boundary, not the VoyageAge Fit Score.

## Phase 3 input

The authoritative company `crawl_summary` JSON contains:

```json
{
  "providers_detected": ["anthropic", "openai"],
  "models_detected": ["claude", "gpt"],
  "strong_signal_count": 8,
  "weak_signal_count": 3,
  "has_api_docs": true,
  "has_ai_docs": true,
  "has_multi_model_signal": true,
  "has_model_selector_signal": true,
  "has_ai_pricing_signal": true,
  "has_ai_jobs_signal": false,
  "llm_integration_signal": true,
  "ai_native_candidate": true,
  "pages_crawled": 7,
  "pages_failed": 1,
  "pages_skipped": 0,
  "crawl_duration_ms": 2190,
  "robots": {"status": "loaded", "url": "https://example.com/robots.txt", "error": null},
  "errors": []
}
```

Phase 3 can combine this summary with normalized evidence rows and page types without interpreting free-form crawler logs or raw website content.
