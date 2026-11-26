from datetime import datetime

from emporio_agent.agent import Reply, ToolCall
from emporio_agent.config import STORE_TZ
from emporio_agent.prompts import build_system_prompt
from emporio_agent.web import to_messages


def test_prompt_when_store_is_closed_and_customer_unknown() -> None:
    sunday = datetime(2026, 11, 29, 10, tzinfo=STORE_TZ)
    prompt = build_system_prompt(sunday, None, None)
    assert "domingo, 29/11/2026 10:00" in prompt
    assert "FECHADA agora" in prompt and "volta amanhã (30/11) às 09:00" in prompt
    assert "Customer not identified." in prompt


def test_prompt_with_identified_customer() -> None:
    wednesday = datetime(2026, 11, 25, 10, tzinfo=STORE_TZ)
    prompt = build_system_prompt(wednesday, "Pedro", "(67) 98432-1098")
    assert "quarta-feira, 25/11/2026 10:00" in prompt
    assert "Customer identified by the channel: Pedro, phone (67) 98432-1098" in prompt


def test_prompt_has_no_hard_coded_store_facts() -> None:
    """Facts must come from tools: no prices, addresses or phone numbers in the prompt."""
    prompt = build_system_prompt(datetime(2026, 11, 25, 10, tzinfo=STORE_TZ), None, None)
    for fact in ("R$", "Rua 14 de Maio", "3341-4444", "3321-4500"):
        assert fact not in prompt


def test_web_shows_tool_calls_as_collapsible_steps() -> None:
    reply = Reply("Custa R$ 2.199,00.", [ToolCall("get_product_details", {"product": "x"}, "{}")])
    messages = to_messages(reply)
    assert [m.metadata.get("title") for m in messages[:-1]] == ["🔧 get_product_details"]
    assert messages[-1].content == "Custa R$ 2.199,00."
