"""
Rihla AI Agent Graph — LangGraph multi-agent pipeline.

Architecture:
  Planner
    ├── Research Agent (OpenAI / web search)
    ├── Sacred Agent   (Claude 3.5 Sonnet — spiritual/halal)
    └── Logistics Agent (GPT-4o — routing/timing)
         └── Cost Agent (Gemini — budgeting)
              └── Writer Agent (Claude — final narrative)

All agents stream tokens via Server-Sent Events.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Annotated, TypedDict, Sequence, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.ai.tools import ALL_TOOLS
from app.ai.prompts import (
    PLANNER_SYSTEM,
    RESEARCH_AGENT_SYSTEM,
    SACRED_AGENT_SYSTEM,
    LOGISTICS_AGENT_SYSTEM,
    COST_AGENT_SYSTEM,
    WRITER_AGENT_SYSTEM,
)

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    trip_id: str
    user_goal: str
    agent_outputs: dict[str, Any]
    current_agent: str
    streaming_steps: list[dict]


# ── Model factory ─────────────────────────────────────────────────────────────

def _get_model(provider: str = "openai", tools: list[BaseTool] | None = None):
    """Create a LLM instance for the given provider, with optional tools bound."""
    try:
        if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                api_key=settings.ANTHROPIC_API_KEY,
                max_tokens=2048,
                streaming=True,
            )
        elif provider == "google" and settings.GOOGLE_AI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=settings.GOOGLE_AI_API_KEY,
                streaming=True,
            )
        else:
            # Default: OpenAI
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY or "placeholder",
                streaming=True,
                temperature=0.7,
            )
    except Exception as exc:
        logger.warning(f"Model init failed ({provider}): {exc}. Falling back to mock.")
        return None

    if tools:
        return llm.bind_tools(tools)
    return llm


# ── Agent node factory ────────────────────────────────────────────────────────

def _make_agent_node(system_prompt: str, provider: str, tools: list[BaseTool], name: str):
    """Create a graph node function for an agent."""
    async def agent_node(state: AgentState) -> dict:
        llm = _get_model(provider, tools)
        if llm is None:
            # Mock response when API key is not set
            mock_msg = AIMessage(content=f"[{name}]: API key not configured. Set {provider.upper()}_API_KEY to enable this agent.")
            return {
                "messages": [mock_msg],
                "agent_outputs": {**state.get("agent_outputs", {}), name: mock_msg.content},
                "current_agent": name,
                "streaming_steps": [*state.get("streaming_steps", []), {"agent": name, "status": "skipped"}],
            }

        trip_context = f"Trip ID: {state['trip_id']}\nUser goal: {state['user_goal']}"
        messages = [
            SystemMessage(content=f"{system_prompt}\n\n{trip_context}"),
            *state["messages"],
        ]

        response = await llm.ainvoke(messages)
        outputs = {**state.get("agent_outputs", {}), name: response.content}

        return {
            "messages": [response],
            "agent_outputs": outputs,
            "current_agent": name,
            "streaming_steps": [
                *state.get("streaming_steps", []),
                {"agent": name, "status": "done", "preview": str(response.content)[:120]},
            ],
        }

    agent_node.__name__ = name
    return agent_node


# ── Build the graph ────────────────────────────────────────────────────────────

def build_rihla_graph() -> StateGraph:
    tool_node = ToolNode(ALL_TOOLS)

    # Agent nodes
    planner = _make_agent_node(PLANNER_SYSTEM, "openai", ALL_TOOLS, "planner")
    research = _make_agent_node(RESEARCH_AGENT_SYSTEM, "openai", [ALL_TOOLS[2]], "research")  # search_place
    sacred = _make_agent_node(SACRED_AGENT_SYSTEM, "anthropic", [ALL_TOOLS[3]], "sacred")   # prayer_times
    logistics = _make_agent_node(LOGISTICS_AGENT_SYSTEM, "openai", [], "logistics")
    cost = _make_agent_node(COST_AGENT_SYSTEM, "google", [ALL_TOOLS[4]], "cost")             # calc split
    writer = _make_agent_node(WRITER_AGENT_SYSTEM, "anthropic", [ALL_TOOLS[1]], "writer")   # update_node

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner)
    graph.add_node("research", research)
    graph.add_node("sacred", sacred)
    graph.add_node("logistics", logistics)
    graph.add_node("cost", cost)
    graph.add_node("writer", writer)
    graph.add_node("tools", tool_node)

    # Linear pipeline: planner → research → sacred → logistics → cost → writer → END
    graph.set_entry_point("planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "sacred")
    graph.add_edge("sacred", "logistics")
    graph.add_edge("logistics", "cost")
    graph.add_edge("cost", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


# Singleton — compiled once
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_rihla_graph()
    return _graph


# ── Streaming runner ──────────────────────────────────────────────────────────

async def stream_enhancement(
    trip_id: str,
    user_goal: str,
    history: list[dict] | None = None,
) -> AsyncIterator[str]:
    """
    Run the full 6-agent enhancement pipeline and yield SSE-compatible chunks.
    Each yielded string is a JSON line prefixed with 'data: '.
    """
    graph = get_graph()

    initial_messages: list[BaseMessage] = [
        HumanMessage(content=f"Please enhance my trip (ID: {trip_id}). Goal: {user_goal}"),
    ]
    if history:
        for msg in history:
            if msg.get("role") == "user":
                initial_messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                initial_messages.append(AIMessage(content=msg["content"]))

    initial_state: AgentState = {
        "messages": initial_messages,
        "trip_id": trip_id,
        "user_goal": user_goal,
        "agent_outputs": {},
        "current_agent": "",
        "streaming_steps": [],
    }

    agent_order = ["planner", "research", "sacred", "logistics", "cost", "writer"]

    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for agent_name, state_update in event.items():
                if agent_name in ("__end__", "tools"):
                    continue

                # Yield agent start event
                yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'step': agent_order.index(agent_name) + 1, 'total': len(agent_order)})}\n\n"

                # Stream the agent's message content
                msgs = state_update.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "content") and msg.content:
                        content = str(msg.content)
                        # Chunk large responses for smoother streaming
                        chunk_size = 50
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'token', 'agent': agent_name, 'content': chunk})}\n\n"

                # Yield agent done event
                yield f"data: {json.dumps({'type': 'agent_done', 'agent': agent_name})}\n\n"

        # Final summary
        yield f"data: {json.dumps({'type': 'done', 'message': 'Enhancement complete. Your trip has been enriched by 6 specialist agents.'})}\n\n"

    except Exception as exc:
        logger.exception(f"AI pipeline error for trip {trip_id}: {exc}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
