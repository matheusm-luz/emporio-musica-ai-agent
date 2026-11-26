"""Generates examples/*.md by running the real agent through scripted conversations.

    uv run python scripts/run_examples.py --model openai:gpt-6-luna

Transcripts are produced by the agent and never edited by hand. Each scenario is also checked with
the same assertions as the eval suite; a scenario that fails is not written, so an example can
never show wrong behaviour.
"""

import argparse
import sys
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from run_evals import check  # noqa: E402

from emporio_agent.agent import Reply, StoreAgent  # noqa: E402
from emporio_agent.config import STORE_TZ, load_settings  # noqa: E402
from emporio_agent.tickets import InMemoryTicketStore  # noqa: E402

EXAMPLES_DIR = ROOT / "examples"
NOW = datetime(2026, 11, 25, 10, 0, tzinfo=STORE_TZ)  # Wednesday, store open

SCENARIOS = [
    {
        "file": "01_catalog_search.md",
        "title": "Catalog search with a price limit",
        "scenario": "A customer looks for acoustic guitars up to R$ 1,000 and then narrows down "
        "to a beginner nylon-string model.",
        "demonstrates": "Data lookup (`search_products`) with category + price filters; "
        "out-of-stock and discontinued items excluded; multi-turn context.",
        "turns": [
            "Oi! Quais opções de violões disponíveis custando até R$1000?",
            "Sou iniciante e prefiro cordas de nylon. Qual você indica?",
        ],
        "expect_tools": ["search_products"],
        "must_include": ["nylon"],
        "must_not_include": ["GF-3D", "SN-7C"],
    },
    {
        "file": "02_store_information.md",
        "title": "General store information",
        "scenario": "A customer asks for the address, Saturday opening hours and the WhatsApp "
        "number.",
        "demonstrates": "Policy lookup (`get_store_policy`) instead of answering from memory; "
        "the manual lists two WhatsApp numbers and both are shown as written (SPEC I12).",
        "turns": [
            "Qual o endereço da loja? Vocês abrem sábado?",
            "E qual o WhatsApp de vocês?",
        ],
        "expect_tools": ["get_store_policy"],
        "must_include": ["3341-4444", "3321-4500"],
    },
    {
        "file": "03_price_and_payment.md",
        "title": "Price check with payment conditions",
        "scenario": "A customer asks the price of the Takamine GD20, then about installments "
        "and paying with PIX.",
        "demonstrates": "Prices computed in code: the product's 12% promotion is inactive so "
        "it is not offered; PIX 5% discount and the maximum installments follow the manual "
        "(§3, §3.1, §6.2).",
        "turns": [
            "Quanto custa o Takamine GD20?",
            "Dá pra parcelar? E se eu pagar no PIX, fica quanto?",
        ],
        "expect_tools": ["get_product_details"],
        "must_include": ["2\\.089,05", "12x|12 vezes"],
        "must_not_include": ["1\\.935"],
    },
    {
        "file": "04_return_request_order_lookup.md",
        "title": "Return request for a real order (non-trivial)",
        "phone": "(67) 98432-1098",
        "scenario": "A customer identified by the WhatsApp number regrets a purchase and asks "
        "to return it, then asks what to do if the instrument has a defect.",
        "demonstrates": "Combines a real-time order lookup (`lookup_orders`, owner-only) with "
        "the return and warranty policies; the 7/30/90-day deadlines are computed in code from "
        "the order dates (§4.1, §4.2, §8).",
        "turns": [
            "Oi! Me arrependi da minha compra, posso devolver meu pedido?",
            "Entendi. E se o violão apresentar algum defeito, o que eu faço?",
        ],
        "expect_tools": ["lookup_orders", "get_store_policy"],
        "must_include": ["fabricante|garantia"],
    },
    {
        "file": "05_out_of_scope_and_promotions_english.md",
        "title": "Out-of-scope requests, an inactive campaign and an English-speaking customer",
        "scenario": "A customer writing in English asks for accessories, Black Friday deals "
        "and something unrelated to the store.",
        "demonstrates": "Scope handling (instruments only, no invented partner stores), "
        "promotions checked against the system (Black Friday is not active), off-topic "
        "refusal, and replying in the customer's language.",
        "turns": [
            "Hi! Do you sell guitar strings and amplifiers?",
            "Ok. Do you have any Black Friday deals right now?",
            "Cool. By the way, who won the last football World Cup?",
        ],
        "expect_tools": ["list_active_promotions"],
        "must_not_include": ["Argentin", "França|France", "Brasil|Brazil"],
    },
]


def render(scenario: dict, model: str, transcript: list[tuple[str, Reply]]) -> str:
    phone = scenario.get("phone")
    identity = f"WhatsApp number {phone}" if phone else "not identified"
    lines = [
        f"# {scenario['title']}",
        "",
        "| | |",
        "|---|---|",
        f"| **Scenario** | {scenario['scenario']} |",
        f"| **Demonstrates** | {scenario['demonstrates']} |",
        f"| **Model** | `{model}` |",
        "| **Agent clock** | Wednesday 25/11/2026 10:00 (America/Campo_Grande) — store open |",
        f"| **Customer identity** | {identity} |",
        "",
        "> Generated by `scripts/run_examples.py` with the real agent — not edited by hand. "
        "Messages are in the customer's language (Brazilian Portuguese unless the customer "
        "writes otherwise); annotations are in English.",
        "",
        "---",
    ]
    for message, reply in transcript:
        lines += ["", f"**👤 Customer:** {message}", ""]
        if reply.tool_calls:
            lines.append(f"<details><summary>🔧 Tools called ({len(reply.tool_calls)})</summary>")
            lines.append("")
            for call in reply.tool_calls:
                output = call.output if len(call.output) <= 600 else call.output[:600] + " …"
                lines.append(f"- `{call.name}` `{call.args}`")
                lines.append(f"  ```json\n  {output}\n  ```")
            lines += ["", "</details>", ""]
        lines.append(f"**🎸 Agent:** {reply.text}")
        lines += ["", "---"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="LLM_MODEL (default: from .env)")
    args = parser.parse_args()
    settings = replace(load_settings(), agent_now=NOW)
    if args.model:
        settings = replace(settings, llm_model=args.model)
    agent = StoreAgent(settings, InMemorySaver(), InMemoryTicketStore())

    EXAMPLES_DIR.mkdir(exist_ok=True)
    failed = 0
    for scenario in SCENARIOS:
        thread = f"example-{uuid.uuid4().hex[:6]}"
        transcript = [
            (turn, agent.reply(thread, turn, customer_phone=scenario.get("phone")))
            for turn in scenario["turns"]
        ]
        failures = check(scenario, [reply for _, reply in transcript])
        if failures:
            failed += 1
            print(f"FAIL {scenario['file']}: {failures} — not written")
            continue
        (EXAMPLES_DIR / scenario["file"]).write_text(
            render(scenario, settings.llm_model, transcript), encoding="utf-8"
        )
        print(f"ok   {scenario['file']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
