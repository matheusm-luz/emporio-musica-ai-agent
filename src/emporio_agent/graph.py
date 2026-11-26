"""LangGraph agent: an explicit ReAct loop (agent <-> tools) plus a deterministic claim check.

    START -> agent --(tool calls)--> tools -> agent ...
                   --(answer)-----> check_claims --(ok)--> END
                                                 --(unbacked claim, once per turn)--> agent

The system prompt is rebuilt on every model call (clock, open/closed status, customer identity),
so only the conversation itself is persisted by the checkpointer.

`check_claims` enforces in code what the prompt can only ask for: the agent must never tell a
customer that a complaint was registered (or quote a protocol) unless `create_support_ticket`
actually ran in this turn. Evals showed a 12B model inventing protocol numbers and deadlines.
"""

import re
from collections.abc import Callable, Sequence
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

MAX_HISTORY_MESSAGES = 40
TICKET_TOOL = "create_support_ticket"
CLAIM_PATTERN = re.compile(
    r"protocolo|registrei|registrad[ao]|reclama[çc][ãa]o (foi )?(aberta|criada)", re.IGNORECASE
)
CORRECTION = (
    "Your previous draft told the customer that a complaint/ticket was registered or quoted a "
    "protocol number, but create_support_ticket was NOT called in this turn, so that would be "
    "false. If the customer wants to register a complaint, call create_support_ticket now and "
    "use only the protocol and deadline it returns. Otherwise, answer without claiming that "
    "anything was registered."
)


class AgentState(MessagesState):
    correction: str | None
    corrected_turn: int | None


def recent_history(
    messages: Sequence[AnyMessage], limit: int = MAX_HISTORY_MESSAGES
) -> list[AnyMessage]:
    """Last `limit` messages, cut at a customer message so no tool result loses its tool call."""
    if len(messages) <= limit:
        return list(messages)
    window = list(messages[-limit:])
    for index, message in enumerate(window):
        if isinstance(message, HumanMessage):
            return window[index:]
    return window[-1:]


def current_turn(messages: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Messages after the customer's latest message."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return list(messages[index + 1 :])
    return list(messages)


def has_unbacked_claim(messages: Sequence[AnyMessage]) -> bool:
    turn = current_turn(messages)
    if not turn or not CLAIM_PATTERN.search(turn[-1].text):
        return False
    called = {c["name"] for m in turn if isinstance(m, AIMessage) for c in m.tool_calls}
    return TICKET_TOOL not in called


def build_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: Callable[[RunnableConfig], str],
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    model_with_tools = model.bind_tools(tools)

    def agent(state: AgentState, config: RunnableConfig) -> dict:
        prompt = [SystemMessage(system_prompt(config)), *recent_history(state["messages"])]
        if state.get("correction"):
            prompt.append(SystemMessage(state["correction"]))
        return {"messages": [model_with_tools.invoke(prompt, config)], "correction": None}

    def route_after_agent(state: AgentState) -> Literal["tools", "check_claims"]:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "check_claims"

    def check_claims(state: AgentState) -> Command[Literal["agent", "__end__"]]:
        messages = state["messages"]
        turn_number = sum(isinstance(m, HumanMessage) for m in messages)
        if has_unbacked_claim(messages) and state.get("corrected_turn") != turn_number:
            return Command(
                goto="agent",
                update={
                    "messages": [RemoveMessage(id=messages[-1].id)],  # drop the false draft
                    "correction": CORRECTION,
                    "corrected_turn": turn_number,
                },
            )
        return Command(goto=END)

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("check_claims", check_claims)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
