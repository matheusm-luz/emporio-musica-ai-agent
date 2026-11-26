"""Model factory: provider selection from LLM_MODEL (no network calls — clients are only built)."""

import pytest
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from emporio_agent.config import Settings
from emporio_agent.llm import GEMINI_OPENAI_BASE_URL, OLLAMA_NUM_CTX, build_chat_model


def test_ollama_model_gets_a_larger_context_window() -> None:
    model = build_chat_model(Settings(llm_model="ollama:gemma4:12b"))
    assert isinstance(model, ChatOllama)
    assert (model.model, model.num_ctx) == ("gemma4:12b", OLLAMA_NUM_CTX)


def test_openai_model_disables_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="openai:gpt-6-luna"))
    assert isinstance(model, ChatOpenAI)
    assert (model.model_name, model.reasoning_effort) == ("gpt-6-luna", "none")


def test_gemini_uses_the_openai_compatible_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    model = build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == GEMINI_OPENAI_BASE_URL
    assert model.model_name == "gemini-3.8-flash"


def test_gemini_requires_its_own_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_chat_model(Settings(llm_model="gemini:gemini-3.8-flash"))


@pytest.mark.parametrize("value", ["gemma4:12b", "ollama:", "azure:gpt"])
def test_invalid_model_strings(value: str) -> None:
    with pytest.raises(ValueError):
        build_chat_model(Settings(llm_model=value))
