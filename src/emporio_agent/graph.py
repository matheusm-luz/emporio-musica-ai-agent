"""LangGraph agent: an explicit two-node ReAct loop (agent <-> tools).

    START -> agent --(tool calls?)--> tools -> agent ... --(no tool calls)--> END

The system prompt is rebuilt on every model call (clock, open/closed status, customer identity),
so only the conversation itself is persisted by the checkpointer.
"""

from collections.abc import Callable, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

MAX_HISTORY_MESSAGES = 40


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


def build_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: Callable[[RunnableConfig], str],
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    model_with_tools = model.bind_tools(tools)

    def agent(state: MessagesState, config: RunnableConfig) -> dict:
        messages = [SystemMessage(system_prompt(config)), *recent_history(state["messages"])]
        return {"messages": [model_with_tools.invoke(messages, config)]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
