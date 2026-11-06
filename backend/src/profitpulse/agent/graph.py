"""LangGraph tool-calling agent for business analytics investigations."""
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from profitpulse.agent.prompts import build_system_prompt
from profitpulse.agent.tools import build_business_tools, build_knowledge_tools
from profitpulse.agent.supply_chain_tools import build_supply_chain_tools


class AgentExecutionError(RuntimeError):
    pass


def build_agent_graph(chat_model, organization_id: str):
    tools = (build_business_tools(organization_id) + build_knowledge_tools(organization_id) + build_supply_chain_tools(organization_id))
    model_with_tools = chat_model.bind_tools(tools)

    def call_model(state: MessagesState) -> dict[str, list[Any]]:
        messages = [SystemMessage(content=build_system_prompt()), *state["messages"]]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "agent")
    return builder.compile(), tools


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    return str(content)


def run_agent(question: str, organization_id: str, max_tool_rounds: int = 6) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, ToolMessage

    from profitpulse.agent.llm import build_chat_model

    from profitpulse.agent.llm import LLMConfigurationError

    try:
        provider, model_name, chat_model = build_chat_model()
        graph, tools = build_agent_graph(chat_model, organization_id)
        tool_names = {tool.name for tool in tools}
        result = graph.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"recursion_limit": max(8, max_tool_rounds * 2 + 4)},
        )
    except LLMConfigurationError:
        raise
    except Exception as exc:
        # Keep provider credentials and internal tracebacks out of the API response.
        raise AgentExecutionError(
            "The AI investigation could not be completed. Check provider availability, model configuration and API logs."
        ) from exc

    messages = result.get("messages", [])
    final_message = messages[-1] if messages else None
    answer = _content_to_text(getattr(final_message, "content", ""))
    if not answer:
        answer = "I could not produce a final answer from the available business data. Please refine the question."

    trace = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in getattr(message, "tool_calls", []) or []:
                name = call.get("name")
                if name in tool_names:
                    trace.append({
                        "tool": name,
                        "arguments": call.get("args", {}),
                    })
    tool_results = sum(1 for message in messages if isinstance(message, ToolMessage))
    retrieved_sources = []
    seen_source_keys = set()
    for message in messages:
        if not isinstance(message, ToolMessage) or getattr(message, "name", "") != "search_knowledge_base":
            continue
        raw_content = _content_to_text(getattr(message, "content", ""))
        try:
            payload = json.loads(raw_content)
        except (TypeError, ValueError):
            continue
        for hit in payload.get("results", []) if isinstance(payload, dict) else []:
            source = hit.get("source", {}) if isinstance(hit, dict) else {}
            key = (source.get("document_id"), source.get("page_number"), source.get("filename"))
            if source and key not in seen_source_keys:
                seen_source_keys.add(key)
                retrieved_sources.append(source)

    return {
        "answer": answer,
        "provider": provider,
        "model": model_name,
        "tools_used": list(dict.fromkeys(item["tool"] for item in trace)),
        "tool_trace": trace,
        "tool_result_count": tool_results,
        "sources": retrieved_sources,
        "disclaimer": "Decision-support analysis based on the connected demo ledger and operational data. Not audited financial, tax, legal, investment or IPO advice.",
    }
