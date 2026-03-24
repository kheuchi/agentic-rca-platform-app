"""LangGraph RCA agent graph definition."""

from langgraph.graph import END, StateGraph

from agent.nodes import (
    correlate_findings,
    execute_tools,
    plan_search,
    should_continue,
    synthesize_root_cause,
)
from agent.state import RCAState


def build_rca_graph() -> StateGraph:
    """Build and compile the RCA agent graph.

    Flow:
        plan_search → execute_tools → correlate_findings → should_continue?
            ├─ "continue" → plan_search (loop)
            └─ "synthesize" → synthesize_root_cause → END
    """
    graph = StateGraph(RCAState)

    graph.add_node("plan_search", plan_search)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("correlate_findings", correlate_findings)
    graph.add_node("synthesize_root_cause", synthesize_root_cause)

    graph.set_entry_point("plan_search")
    graph.add_edge("plan_search", "execute_tools")
    graph.add_edge("execute_tools", "correlate_findings")

    graph.add_conditional_edges(
        "correlate_findings",
        should_continue,
        {
            "continue": "plan_search",
            "synthesize": "synthesize_root_cause",
        },
    )

    graph.add_edge("synthesize_root_cause", END)

    return graph.compile()


rca_agent = build_rca_graph()
