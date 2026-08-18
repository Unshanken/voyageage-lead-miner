import hashlib
import re
from dataclasses import dataclass

from leadminer.models import PageType, SignalContext
from leadminer.signals.patterns import (
    AI_JOB_PATTERN,
    AI_PRICING_PATTERN,
    CONCEPT_PATTERNS,
    INTEGRATION_LANGUAGE,
    MODEL_PATTERNS,
    MULTI_MODEL_LANGUAGE,
    PROVIDER_PATTERNS,
    SDK_PATTERNS,
)

DETECTOR_VERSION = "deterministic-v1"


@dataclass(frozen=True, slots=True)
class DetectedSignal:
    signal_type: str
    signal_key: str
    value: str
    evidence_text: str
    confidence: float
    context: SignalContext
    evidence_hash: str
    detector: str = DETECTOR_VERSION


def detect_signals(
    text: str,
    page_type: PageType,
    title: str | None = None,
    headings: list[str] | None = None,
) -> list[DetectedSignal]:
    content = " ".join(part for part in [title or "", " ".join(headings or []), text] if part)
    detected: dict[tuple[str, str], DetectedSignal] = {}

    for provider, pattern in PROVIDER_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = _snippet(content, match.start(), match.end())
            context, confidence = _context_confidence(page_type, snippet)
            _keep_best(detected, _signal("provider", provider, snippet, confidence, context))

    for model, pattern in MODEL_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = _snippet(content, match.start(), match.end())
            context, confidence = _context_confidence(page_type, snippet)
            _keep_best(detected, _signal("model", model, snippet, confidence, context))

    for provider, pattern in SDK_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = _snippet(content, match.start(), match.end())
            _keep_best(
                detected,
                _signal(
                    "integration",
                    provider,
                    snippet,
                    0.99,
                    SignalContext.EXPLICIT_INTEGRATION,
                ),
            )
            _keep_best(
                detected,
                _signal(
                    "provider",
                    provider,
                    snippet,
                    0.98,
                    SignalContext.EXPLICIT_INTEGRATION,
                ),
            )

    for concept, pattern in CONCEPT_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = _snippet(content, match.start(), match.end())
            context, confidence = _context_confidence(
                page_type, snippet, generic=True, concept=concept
            )
            _keep_best(detected, _signal("concept", concept, snippet, confidence, context))

    model_keys = {key for signal_type, key in detected if signal_type == "model"}
    provider_keys = {key for signal_type, key in detected if signal_type == "provider"}
    multi_match = MULTI_MODEL_LANGUAGE.search(content)
    if len(model_keys) >= 2 or len(provider_keys) >= 2 or multi_match:
        match = multi_match or _first_model_span(content)
        snippet = _snippet(content, match.start(), match.end()) if match else content[:240]
        confidence = 0.94 if len(model_keys) >= 2 or len(provider_keys) >= 2 else 0.82
        _keep_best(
            detected,
            _signal("product", "multi_model", snippet, confidence, SignalContext.PRODUCT_FEATURE),
        )
    selector_match = re.search(
        r"model selector|choose (?:between|from)|switch between models?", content, re.I
    )
    if selector_match:
        snippet = _snippet(content, selector_match.start(), selector_match.end())
        _keep_best(
            detected,
            _signal("product", "model_selector", snippet, 0.9, SignalContext.PRODUCT_FEATURE),
        )

    if page_type == PageType.PRICING and (match := AI_PRICING_PATTERN.search(content)):
        snippet = _snippet(content, match.start(), match.end())
        _keep_best(
            detected,
            _signal("commercial", "ai_pricing", snippet, 0.96, SignalContext.PRICING_FEATURE),
        )
    if page_type == PageType.CAREERS and (match := AI_JOB_PATTERN.search(content)):
        snippet = _snippet(content, match.start(), match.end())
        _keep_best(
            detected,
            _signal("careers", "ai_job", snippet, 0.94, SignalContext.CAREERS_SIGNAL),
        )
    return sorted(
        detected.values(), key=lambda item: (-item.confidence, item.signal_type, item.signal_key)
    )


def _context_confidence(
    page_type: PageType,
    snippet: str,
    generic: bool = False,
    concept: str | None = None,
) -> tuple[SignalContext, float]:
    if page_type == PageType.BLOG:
        return SignalContext.EDITORIAL_MENTION, 0.32 if generic else 0.38
    if page_type in {PageType.DOCS, PageType.API_DOCS}:
        return SignalContext.TECHNICAL_DOCS, 0.7 if generic else 0.9
    if page_type == PageType.PRICING:
        return SignalContext.PRICING_FEATURE, 0.78 if generic else 0.84
    if page_type == PageType.CAREERS:
        return SignalContext.CAREERS_SIGNAL, 0.62 if generic else 0.68
    if page_type in {
        PageType.HOME,
        PageType.PRODUCT,
        PageType.FEATURES,
        PageType.INTEGRATIONS,
        PageType.MODELS,
    }:
        integration = bool(INTEGRATION_LANGUAGE.search(snippet))
        if generic and concept in {"ai_agent", "ai_assistant", "generative_ai", "llm"}:
            return SignalContext.PRODUCT_FEATURE, 0.82
        return SignalContext.PRODUCT_FEATURE, (0.8 if integration else 0.62) - (
            0.08 if generic else 0
        )
    return SignalContext.GENERIC_MENTION, 0.48 if generic else 0.56


def _signal(
    signal_type: str,
    key: str,
    snippet: str,
    confidence: float,
    context: SignalContext,
) -> DetectedSignal:
    normalized = re.sub(r"\s+", " ", snippet).strip()[:320]
    evidence_hash = hashlib.sha256(f"{signal_type}|{key}|{normalized.lower()}".encode()).hexdigest()
    return DetectedSignal(
        signal_type=signal_type,
        signal_key=key,
        value="true",
        evidence_text=normalized,
        confidence=round(confidence, 2),
        context=context,
        evidence_hash=evidence_hash,
    )


def _keep_best(items: dict[tuple[str, str], DetectedSignal], candidate: DetectedSignal) -> None:
    key = (candidate.signal_type, candidate.signal_key)
    current = items.get(key)
    if current is None or candidate.confidence > current.confidence:
        items[key] = candidate


def _snippet(content: str, start: int, end: int, radius: int = 115) -> str:
    left = max(0, start - radius)
    right = min(len(content), end + radius)
    snippet = re.sub(r"\s+", " ", content[left:right]).strip()
    return f"…{snippet}…" if left or right < len(content) else snippet


def _first_model_span(content: str) -> re.Match[str] | None:
    matches = [pattern.search(content) for pattern in MODEL_PATTERNS.values()]
    return min((match for match in matches if match), key=lambda match: match.start(), default=None)
