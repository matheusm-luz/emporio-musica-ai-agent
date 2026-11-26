"""Chat-model factory: one config value, `LLM_MODEL="<provider>:<model>"`, switches between a
free local model (Ollama), OpenAI, and Google Gemini's free tier. The rest of the code never knows
which one is in use."""

import os

from langchain_core.language_models import BaseChatModel

from emporio_agent.config import Settings

# Ollama's default context window is small; system prompt + 6 tool schemas + history + policy
# sections need more. 16k fits a 12B model plus KV cache in 16 GB of VRAM.
OLLAMA_NUM_CTX = 16_384

# Gemini exposes an OpenAI-compatible endpoint, so the same client is reused (no extra dependency).
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def build_chat_model(settings: Settings) -> BaseChatModel:
    provider, _, model = settings.llm_model.partition(":")
    if not model:
        raise ValueError(f"LLM_MODEL must be '<provider>:<model>', got '{settings.llm_model}'")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, base_url=settings.ollama_base_url, num_ctx=OLLAMA_NUM_CTX)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        # Low latency for chat: no reasoning tokens. On gpt-6-luna, Chat Completions supports
        # function calling only with reasoning_effort="none".
        return ChatOpenAI(model=model, reasoning_effort="none")

    if provider == "gemini":
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set (free key: https://aistudio.google.com)")
        # Gemini 3.x thinking cannot be disabled; "low" is its fastest setting. Extra retries
        # absorb the free tier's per-minute rate limits.
        return ChatOpenAI(
            model=model,
            base_url=GEMINI_OPENAI_BASE_URL,
            api_key=api_key,
            reasoning_effort="low",
            max_retries=6,
        )

    raise ValueError(f"Unsupported LLM provider '{provider}' (use 'ollama', 'openai' or 'gemini')")
