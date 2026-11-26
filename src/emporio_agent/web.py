"""Minimal web chat (Gradio): `uv run emporio-web` -> http://localhost:7860

Each browser session is its own conversation thread; tool calls are shown as collapsible steps.
"""

import json
import logging

import gradio as gr

from emporio_agent.agent import Reply, StoreAgent, open_agent
from emporio_agent.config import load_settings

EXAMPLES = [
    ["Quais opções de violões disponíveis custando até R$1000?", ""],
    ["Quanto custa o Takamine GD20? Dá pra parcelar?", ""],
    ["Me arrependi da minha compra, posso devolver meu pedido?", "(67) 98432-1098"],
    ["Vocês estão com desconto de Black Friday?", ""],
    ["Vocês vendem cordas e amplificador?", ""],
]


def to_messages(reply: Reply) -> list[gr.ChatMessage]:
    steps = [
        gr.ChatMessage(
            role="assistant",
            content=f"```json\n{json.dumps(call.args, ensure_ascii=False)}\n```\n"
            f"{call.output[:1500]}",
            metadata={"title": f"🔧 {call.name}", "status": "done"},
        )
        for call in reply.tool_calls
    ]
    return [*steps, gr.ChatMessage(role="assistant", content=reply.text)]


def build_app(agent: StoreAgent, model_name: str) -> gr.ChatInterface:
    def respond(message: str, history: list, phone: str, request: gr.Request) -> list:
        thread_id = f"web-{request.session_hash}"
        return to_messages(agent.reply(thread_id, message, customer_phone=phone.strip() or None))

    return gr.ChatInterface(
        respond,
        title="🎸 Empório da Música — assistente virtual",
        description=(
            f"Protótipo de atendimento · modelo `{model_name}`. "
            "Informe um telefone abaixo para simular um cliente identificado pelo WhatsApp."
        ),
        additional_inputs=[
            gr.Textbox(
                label="Telefone do cliente (simula o WhatsApp)", placeholder="(67) 98432-1098"
            )
        ],
        additional_inputs_accordion=gr.Accordion("Cliente", open=False),
        examples=EXAMPLES,
        cache_examples=False,
        fill_height=True,
    )


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    settings = load_settings()
    with open_agent(settings) as agent:
        build_app(agent, settings.llm_model).launch()


if __name__ == "__main__":
    main()
