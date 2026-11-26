"""Agent facade used by every interface (CLI, web UI, evals, example generation)."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import psycopg
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from emporio_agent.config import Settings
from emporio_agent.data import load_store_data
from emporio_agent.graph import build_graph
from emporio_agent.llm import build_chat_model
from emporio_agent.policies import PolicyManual
from emporio_agent.prompts import build_system_prompt
from emporio_agent.tickets import InMemoryTicketStore, PostgresTicketStore, TicketStore
from emporio_agent.tools import build_tools, customer_first_name

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 16  # max graph steps per customer message — stops runaway tool loops


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]
    output: str


@dataclass(frozen=True)
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class StoreAgent:
    def __init__(
        self,
        settings: Settings,
        checkpointer: BaseCheckpointSaver,
        tickets: TicketStore,
        model: BaseChatModel | None = None,
    ) -> None:
        self.settings = settings
        self.history_backend = "Postgres" if isinstance(checkpointer, PostgresSaver) else "memória"
        self.store = load_store_data()
        self.manual = PolicyManual.load()
        tools = build_tools(self.store, self.manual, tickets, settings.now)
        self.graph = build_graph(
            model or build_chat_model(settings), tools, self._system_prompt, checkpointer
        )

    def _system_prompt(self, config: RunnableConfig) -> str:
        phone = config.get("configurable", {}).get("customer_phone")
        name = customer_first_name(self.store, phone) if phone else None
        return build_system_prompt(self.settings.now(), name, phone)

    def reply(self, thread_id: str, text: str, customer_phone: str | None = None) -> Reply:
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id, "customer_phone": customer_phone},
            "recursion_limit": RECURSION_LIMIT,
        }
        previous = len(self.graph.get_state(config).values.get("messages", []))
        state = self.graph.invoke({"messages": [HumanMessage(text)]}, config)
        new_messages = state["messages"][previous + 1 :]

        outputs = {m.tool_call_id: m.text for m in new_messages if isinstance(m, ToolMessage)}
        calls = [
            ToolCall(call["name"], call["args"], outputs.get(call["id"], ""))
            for m in new_messages
            if isinstance(m, AIMessage)
            for call in m.tool_calls
        ]
        return Reply(text=state["messages"][-1].text, tool_calls=calls)

    def history(self, thread_id: str) -> list[tuple[str, str]]:
        """(role, text) pairs of a stored conversation, tool traffic omitted."""
        state = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        pairs = []
        for message in state.values.get("messages", []):
            if isinstance(message, HumanMessage):
                pairs.append(("user", message.text))
            elif isinstance(message, AIMessage) and message.text and not message.tool_calls:
                pairs.append(("assistant", message.text))
        return pairs


def _postgres_reachable(database_url: str) -> bool:
    try:
        psycopg.connect(database_url, connect_timeout=3).close()
        return True
    except psycopg.OperationalError as exc:
        logger.warning("Postgres unavailable (%s) — using in-memory history", exc)
        return False


@contextmanager
def open_agent(settings: Settings, model: BaseChatModel | None = None) -> Iterator[StoreAgent]:
    """Agent with Postgres persistence when DATABASE_URL is reachable, in-memory otherwise."""
    if settings.database_url and _postgres_reachable(settings.database_url):
        with PostgresSaver.from_conn_string(settings.database_url) as checkpointer:
            checkpointer.setup()
            tickets = PostgresTicketStore(settings.database_url)
            yield StoreAgent(settings, checkpointer, tickets, model)
    else:
        yield StoreAgent(settings, InMemorySaver(), InMemoryTicketStore(), model)


def tool_call_preview(call: ToolCall, limit: int = 300) -> str:
    args = json.dumps(call.args, ensure_ascii=False)
    output = call.output if len(call.output) <= limit else call.output[:limit] + "…"
    return f"{call.name}({args}) -> {output}"
