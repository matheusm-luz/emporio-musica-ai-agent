"""Chat-model factory: one config value, `LLM_MODEL="<provider>:<model>"`, switches between a
free local model (Ollama) and OpenAI. The rest of the code never knows which one is in use."""

from langchain_core.language_models import BaseChatModel

from emporio_agent.config import Settings

# Ollama's default context window is small; system prompt + 6 tool schemas + history + policy
# sections need more. 16k fits a 12B model plus KV cache in 16 GB of VRAM.
OLLAMA_NUM_CTX = 16_384


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

    raise ValueError(f"Unsupported LLM provider '{provider}' (use 'ollama' or 'openai')")
