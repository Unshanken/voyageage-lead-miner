import re

PROVIDER_PATTERNS = {
    "openai": re.compile(r"\bopenai\b|api\.openai\.com|OPENAI_API_KEY", re.I),
    "anthropic": re.compile(r"\banthropic\b|api\.anthropic\.com|ANTHROPIC_API_KEY", re.I),
    "google": re.compile(
        r"\bgoogle\s+gemini\b|generativelanguage\.googleapis\.com|GEMINI_API_KEY", re.I
    ),
    "deepseek": re.compile(r"\bdeepseek\b", re.I),
    "meta": re.compile(r"\bmeta(?:'s)?\s+llama\b|\bllama\s*[23]?\b", re.I),
    "openrouter": re.compile(r"\bopenrouter\b|openrouter\.ai/api", re.I),
    "mistral": re.compile(r"\bmistral(?:\s+ai)?\b", re.I),
    "cohere": re.compile(r"\bcohere\b", re.I),
    "xai": re.compile(r"\bxai\b|\bxAI\b|\bgrok\b", re.I),
}

MODEL_PATTERNS = {
    "gpt": re.compile(r"\bGPT(?:-[A-Z0-9.]+)?\b", re.I),
    "claude": re.compile(r"\bClaude(?:\s+[0-9.]+|\s+(?:Opus|Sonnet|Haiku))?\b", re.I),
    "gemini": re.compile(r"\bGemini(?:\s+[0-9.]+|\s+(?:Pro|Flash|Ultra))?\b", re.I),
    "deepseek": re.compile(r"\bDeepSeek(?:-[A-Z0-9.]+)?\b", re.I),
    "llama": re.compile(r"\bLlama(?:\s+[0-9.]+)?\b", re.I),
    "mistral": re.compile(r"\bMistral(?:\s+[A-Z0-9.]+)?\b", re.I),
    "grok": re.compile(r"\bGrok(?:\s+[0-9.]+)?\b", re.I),
}

CONCEPT_PATTERNS = {
    "llm": re.compile(r"\bLLMs?\b|large language models?|foundation models?", re.I),
    "generative_ai": re.compile(r"\bgenerative AI\b|\bAI models?\b", re.I),
    "ai_agent": re.compile(r"\bAI agents?\b|\bagentic\b|\bagent engineer", re.I),
    "ai_assistant": re.compile(r"\bAI assistants?\b|\bAI copilots?\b|\bAI chatbots?\b", re.I),
    "prompt": re.compile(r"\bprompt(?:ing|s)?\b", re.I),
    "tokens": re.compile(r"\btokens?\b|context windows?", re.I),
    "inference": re.compile(r"\binference\b", re.I),
    "embeddings": re.compile(r"\bembeddings?\b|\brerank(?:er|ing)?\b", re.I),
    "tool_calling": re.compile(r"\btool calling\b|\bfunction calling\b", re.I),
}

SDK_PATTERNS = {
    "openai": re.compile(
        r"from\s+openai\s+import\s+OpenAI|import\s+openai|import\s+OpenAI\s+from\s+['\"]openai['\"]|OPENAI_API_KEY|api\.openai\.com",
        re.I,
    ),
    "anthropic": re.compile(
        r"from\s+anthropic\s+import\s+Anthropic|@anthropic-ai/sdk|ANTHROPIC_API_KEY|api\.anthropic\.com",
        re.I,
    ),
    "google": re.compile(r"GEMINI_API_KEY|generativelanguage\.googleapis\.com", re.I),
    "openrouter": re.compile(r"openrouter\.ai/api|OPENROUTER_API_KEY", re.I),
}

INTEGRATION_LANGUAGE = re.compile(
    r"integrat(?:e|es|ed|ion)|connect(?:s|ed)?|supported providers?|bring your own|"
    r"api key|sdk|powered by|choose (?:between|from)|select (?:a )?model|model selector",
    re.I,
)

MULTI_MODEL_LANGUAGE = re.compile(
    r"model selector|choose (?:between|from)|switch between models?|multiple (?:AI )?models?|"
    r"supported providers?|bring your own (?:OpenAI|Anthropic)",
    re.I,
)

AI_PRICING_PATTERN = re.compile(
    r"(?:[\d,]+\s+)?(?:AI|generation|model|token) credits?(?:\s*/\s*month)?|"
    r"credits? per generation|model usage|LLM usage|usage-based pricing",
    re.I,
)

AI_JOB_PATTERN = re.compile(
    r"\b(?:Senior\s+|Staff\s+|Principal\s+)?(?:AI|ML|Machine Learning|LLM|Applied AI|"
    r"AI Infrastructure|Inference|Prompt|Agent)\s+(?:Engineer|Researcher|Scientist)\b",
    re.I,
)
