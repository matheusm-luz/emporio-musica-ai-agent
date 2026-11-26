"""Chat-model factory: one config value, `LLM_MODEL="<provider>:<model>"`, switches between a
free local model (Ollama), OpenAI, and Google Gemini's free tier. The rest of the code never knows
which one is in use."""

import os
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI

from emporio_agent.config import Settings

# Ollama's default context window is small; system prompt + 6 tool schemas + history + policy
# sections need more. 16k fits a 12B model plus KV cache in 16 GB of VRAM.
OLLAMA_NUM_CTX = 16_384

# Gemini exposes an OpenAI-compatible endpoint, so the same client is reused (no extra dependency).
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# additional_kwargs key keeping each Gemini tool call's `extra_content` (thought signature).
TOOL_CALL_EXTRA_CONTENT = "tool_call_extra_content"


class GeminiChatOpenAI(ChatOpenAI):
    """ChatOpenAI for Gemini's OpenAI-compatible endpoint.

    Gemini 3+ attaches a thought signature to each tool call (`tool_calls[].extra_content`) and
    rejects the next request with HTTP 400 unless it is sent back. langchain-openai drops unknown
    fields, so the signature is stored in `additional_kwargs` (persisted with the conversation)
    and re-attached to the matching tool call (by id) in every outgoing request.
    """

    def _create_chat_result(self, response: Any, generation_info: dict | None = None) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        raw = response if isinstance(response, dict) else response.model_dump()
        for generation, choice in zip(result.generations, raw["choices"], strict=False):
            extras = {
                call["id"]: call["extra_content"]
                for call in choice["message"].get("tool_calls") or []
                if call.get("extra_content")
            }
            if extras:
                generation.message.additional_kwargs[TOOL_CALL_EXTRA_CONTENT] = extras
        return result

    def _get_request_payload(
        self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        extras: dict[str, Any] = {}
        for message in self._convert_input(input_).to_messages():
            if isinstance(message, AIMessage):
                extras.update(message.additional_kwargs.get(TOOL_CALL_EXTRA_CONTENT, {}))
        for message in payload.get("messages", []):
            for call in message.get("tool_calls") or []:
                if call.get("id") in extras:
                    call["extra_content"] = extras[call["id"]]
        return payload


def build_chat_model(settings: Settings) -> BaseChatModel:
    provider, _, model = settings.llm_model.partition(":")
    if not model:
        raise ValueError(f"LLM_MODEL must be '<provider>:<model>', got '{settings.llm_model}'")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, base_url=settings.ollama_base_url, num_ctx=OLLAMA_NUM_CTX)

    if provider == "openai":
        # Low latency for chat: no reasoning tokens. On gpt-6-luna, Chat Completions supports
        # function calling only with reasoning_effort="none". With parallel tool calls it added
        # an argument-less search_products next to the real calls (e.g. "address + Saturday
        # hours?"), so calls are made one at a time.
        return ChatOpenAI(
            model=model, reasoning_effort="none", model_kwargs={"parallel_tool_calls": False}
        )

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set (free key: https://aistudio.google.com)")
        # Gemini 3.x thinking cannot be disabled; "low" is its fastest setting. Extra retries
        # absorb the free tier's per-minute rate limits.
        return GeminiChatOpenAI(
            model=model,
            base_url=GEMINI_OPENAI_BASE_URL,
            api_key=api_key,
            reasoning_effort="low",
            max_retries=6,
        )

    raise ValueError(f"Unsupported LLM provider '{provider}' (use 'ollama', 'openai' or 'gemini')")
