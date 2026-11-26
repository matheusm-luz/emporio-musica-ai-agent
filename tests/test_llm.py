"""Model factory: provider selection from LLM_MODEL (no network calls — clients are only built)."""

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from emporio_agent.config import Settings
from emporio_agent.llm import (
    GEMINI_OPENAI_BASE_URL,
    OLLAMA_NUM_CTX,
    TOOL_CALL_EXTRA_CONTENT,
    GeminiChatOpenAI,
    build_chat_model,
)


def test_ollama_model_gets_a_larger_context_window() -> None:
    model = build_chat_model(Settings(llm_model="ollama:gemma4:12b"))
    assert isinstance(model, ChatOllama)
    assert (model.model, model.num_ctx) == ("gemma4:12b", OLLAMA_NUM_CTX)


def test_openai_model_disables_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="openai:gpt-6-luna"))
    assert isinstance(model, ChatOpenAI)
    assert (model.model_name, model.reasoning_effort) == ("gpt-6-luna", "none")
    assert model.model_kwargs == {"parallel_tool_calls": False}


def test_gemini_uses_the_openai_compatible_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))
    assert isinstance(model, GeminiChatOpenAI)
    assert model.openai_api_base == GEMINI_OPENAI_BASE_URL
    assert model.model_name == "gemini-3.8-flash"


def test_gemini_requires_its_own_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))


SIGNATURE = {"google": {"thought_signature": "c2lnbmF0dXJl"}}


def gemini_tool_call_response() -> dict:
    """A Gemini OpenAI-compatible response with one tool call carrying a thought signature."""
    call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_store_policy", "arguments": '{"topic": "trocas"}'},
        "extra_content": SIGNATURE,
    }
    message = {"role": "assistant", "content": None, "tool_calls": [call]}
    return {"choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}]}


def test_gemini_sends_the_thought_signature_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini 3+ rejects a follow-up request (HTTP 400) whose tool call lacks its signature."""
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))

    ai = model._create_chat_result(gemini_tool_call_response()).generations[0].message
    assert ai.tool_calls[0]["id"] == "call_1"
    assert ai.additional_kwargs[TOOL_CALL_EXTRA_CONTENT] == {"call_1": SIGNATURE}

    history = [
        HumanMessage("Como funciona a troca?"),
        ai,
        ToolMessage("...", tool_call_id="call_1"),
    ]
    payload = model._get_request_payload(history)
    sent = next(m for m in payload["messages"] if m.get("tool_calls"))
    assert sent["tool_calls"][0]["extra_content"] == SIGNATURE


def test_tool_calls_without_signature_are_sent_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))
    response = gemini_tool_call_response()
    del response["choices"][0]["message"]["tool_calls"][0]["extra_content"]

    ai = model._create_chat_result(response).generations[0].message
    assert TOOL_CALL_EXTRA_CONTENT not in ai.additional_kwargs
    payload = model._get_request_payload([HumanMessage("oi"), ai])
    sent = next(m for m in payload["messages"] if m.get("tool_calls"))
    assert "extra_content" not in sent["tool_calls"][0]


@pytest.mark.parametrize("value", ["gemma4:12b", "ollama:", "azure:gpt"])
def test_invalid_model_strings(value: str) -> None:
    with pytest.raises(ValueError):
        build_chat_model(Settings(llm_model=value))
