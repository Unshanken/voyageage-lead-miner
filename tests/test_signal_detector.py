from pathlib import Path

import pytest
from leadminer.crawler.extract import extract_html
from leadminer.models import PageType, SignalContext
from leadminer.signals import detect_signals

FIXTURES = Path(__file__).parent / "fixtures" / "pages"


def signals_for(name: str, page_type: PageType):
    extracted = extract_html(
        (FIXTURES / name).read_text(encoding="utf-8"),
        f"https://example.test/{name}",
        "example.test",
        12_000,
    )
    return detect_signals(extracted.visible_text, page_type, extracted.title, extracted.headings)


def find(signals, signal_type: str, key: str):
    return next(
        item for item in signals if item.signal_type == signal_type and item.signal_key == key
    )


def test_openai_sdk_is_strong_explicit_integration() -> None:
    signals = signals_for("openai_docs.html", PageType.API_DOCS)
    evidence = find(signals, "provider", "openai")
    assert evidence.confidence >= 0.98
    assert evidence.context == SignalContext.EXPLICIT_INTEGRATION
    assert find(signals, "integration", "openai")


def test_anthropic_and_claude_detection() -> None:
    signals = signals_for("anthropic_docs.html", PageType.DOCS)
    assert find(signals, "provider", "anthropic").confidence >= 0.98
    assert find(signals, "model", "claude").confidence >= 0.8


def test_multi_model_and_selector_detection() -> None:
    signals = signals_for("multi_model.html", PageType.MODELS)
    assert {"gpt", "claude", "gemini"}.issubset(
        {item.signal_key for item in signals if item.signal_type == "model"}
    )
    assert find(signals, "product", "multi_model").confidence >= 0.9
    assert find(signals, "product", "model_selector").confidence >= 0.9


def test_editorial_mention_stays_weak() -> None:
    signals = signals_for("editorial.html", PageType.BLOG)
    openai = find(signals, "provider", "openai")
    assert openai.context == SignalContext.EDITORIAL_MENTION
    assert openai.confidence < 0.5
    assert not any(item.signal_type == "integration" for item in signals)


def test_generic_smart_automation_does_not_trigger_ai() -> None:
    assert signals_for("non_ai.html", PageType.HOME) == []


@pytest.mark.parametrize(
    ("fixture", "page_type", "signal_type", "key"),
    [
        ("careers.html", PageType.CAREERS, "careers", "ai_job"),
        ("pricing.html", PageType.PRICING, "commercial", "ai_pricing"),
    ],
)
def test_specialized_page_signals(
    fixture: str, page_type: PageType, signal_type: str, key: str
) -> None:
    assert find(signals_for(fixture, page_type), signal_type, key).confidence >= 0.9
