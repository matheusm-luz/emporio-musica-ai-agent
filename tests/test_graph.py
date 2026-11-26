"""Agent loop tests with a scripted chat model — no LLM, no network."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

from emporio_agent.agent import StoreAgent
from emporio_agent.config import STORE_TZ, Settings
from emporio_agent.graph import recent_history
from emporio_agent.tickets import InMemoryTicketStore


class ScriptedChatModel(BaseChatModel):
    """Returns the scripted messages in order and records every prompt it receives."""

    script: list[AIMessage]
    received: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])


def _agent(script: list[AIMessage]) -> tuple[StoreAgent, ScriptedChatModel]:
    model = ScriptedChatModel(script=script, received=[])
    settings = Settings(agent_now=datetime(2026, 11, 25, 10, tzinfo=STORE_TZ))
    return StoreAgent(settings, InMemorySaver(), InMemoryTicketStore(), model), model


def test_tool_call_round_trip_and_persisted_history() -> None:
    call = {"name": "get_product_details", "args": {"product": "Takamine GD20"}, "id": "call-1"}
    agent, model = _agent(
        [
            AIMessage(content="", tool_calls=[call]),
            AIMessage(content="O Takamine GD20 custa R$ 2.199,00."),
            AIMessage(content="De nada!"),
        ]
    )

    reply = agent.reply("thread-1", "Quanto custa o Takamine GD20?")
    assert reply.text == "O Takamine GD20 custa R$ 2.199,00."
    assert [c.name for c in reply.tool_calls] == ["get_product_details"]
    assert "R$ 2.199,00" in reply.tool_calls[0].output

    # the model saw the real tool result
    tool_results = [m for m in model.received[1] if isinstance(m, ToolMessage)]
    assert "R$ 2.199,00" in tool_results[0].text

    # second turn: same thread keeps the history, fresh system prompt on every call
    second = agent.reply("thread-1", "Obrigado!")
    assert second.text == "De nada!" and second.tool_calls == []
    last_prompt = model.received[-1]
    assert "ABERTA agora" in last_prompt[0].text
    assert [m.text for m in last_prompt if isinstance(m, HumanMessage)] == [
        "Quanto custa o Takamine GD20?",
        "Obrigado!",
    ]
    assert agent.history("thread-1") == [
        ("user", "Quanto custa o Takamine GD20?"),
        ("assistant", "O Takamine GD20 custa R$ 2.199,00."),
        ("user", "Obrigado!"),
        ("assistant", "De nada!"),
    ]


def test_customer_identified_by_channel_is_in_the_prompt() -> None:
    agent, model = _agent([AIMessage(content="Olá, Pedro!")])
    agent.reply("thread-2", "Oi", customer_phone="(67) 98432-1098")
    assert "Customer identified by the channel: Pedro" in model.received[0][0].text


def test_unbacked_ticket_claim_is_corrected_once() -> None:
    """A draft that invents a protocol is discarded and the model is asked to really do it."""
    ticket_call = {
        "name": "create_support_ticket",
        "args": {"kind": "reclamacao", "summary": "Atraso", "customer_contact": "x"},
        "id": "call-t",
    }
    agent, model = _agent(
        [
            AIMessage(content="Já registrei sua reclamação, protocolo #928374."),  # fabricated
            AIMessage(content="", tool_calls=[ticket_call]),
            AIMessage(content="Reclamação registrada: protocolo EMP-20261125-0001."),
        ]
    )
    reply = agent.reply("thread-c", "Quero registrar uma reclamação!")

    assert [c.name for c in reply.tool_calls] == ["create_support_ticket"]
    assert reply.text == "Reclamação registrada: protocolo EMP-20261125-0001."
    assert "create_support_ticket was NOT called" in model.received[1][-1].text
    history = [text for _, text in agent.history("thread-c")]
    assert not any("928374" in text for text in history)  # the false draft is not persisted


def test_claim_check_does_not_loop() -> None:
    agent, model = _agent(
        [AIMessage(content="Protocolo #1."), AIMessage(content="Protocolo #2, de novo.")]
    )
    reply = agent.reply("thread-d", "Quero reclamar")
    assert reply.text == "Protocolo #2, de novo."  # one correction per turn, then it stops
    assert len(model.received) == 2


def test_answer_without_claims_ends_normally() -> None:
    agent, model = _agent([AIMessage(content="Abrimos de segunda a sexta.")])
    assert agent.reply("thread-e", "Que horas abrem?").text == "Abrimos de segunda a sexta."
    assert len(model.received) == 1


def test_recent_history_never_starts_with_an_orphan_tool_result() -> None:
    call = {"name": "x", "args": {}, "id": "c"}
    messages = [
        HumanMessage("a"),
        AIMessage(content="", tool_calls=[call]),
        ToolMessage("r", tool_call_id="c"),
        AIMessage(content="b"),
        HumanMessage("c"),
        AIMessage(content="d"),
    ]
    assert recent_history(messages, limit=4) == messages[4:]
    assert recent_history(messages, limit=10) == messages
