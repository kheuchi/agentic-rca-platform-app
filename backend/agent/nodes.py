"""LangGraph node functions for the RCA agent."""

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage

from agent.state import RCAState
from llm.providers import get_chat_llm
from llm.tracing import build_langchain_config

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """\
You are an RCA (Root Cause Analysis) planner for a microservices application \
(OpenTelemetry Astronomy Shop). You have access to these tools:

- search_code_vectors: Search source code for relevant functions, error handlers, etc.
- query_opensearch_logs: Query application logs via OpenSearch.
- query_prometheus_metrics: Query metrics via PromQL (error rates, latency, saturation).
- query_jaeger_traces: Search distributed traces (errors, slow requests).

Given the user's question and any evidence gathered so far, decide which tools \
to call next. Return a JSON object with a "tools" array. Each tool entry must \
have "name" and "args" keys. Only include tools that will provide NEW information.

If you already have sufficient evidence to identify the root cause, return \
{"tools": [], "ready": true}.

Example:
{"tools": [
  {"name": "query_opensearch_logs", "args": {"service_name": "frontendproxy", "query_string": "error OR exception", "lookback_minutes": 60}},
  {"name": "search_code_vectors", "args": {"query": "checkout error handling", "service_filter": "checkoutservice"}}
], "ready": false}
"""

CORRELATE_SYSTEM_PROMPT = """\
You are an RCA analyst. You have gathered evidence from code, logs, metrics, \
and traces for a microservices application. Analyze ALL evidence and produce \
hypotheses about the root cause.

For each hypothesis, explain:
1. What the evidence suggests
2. Which service(s) are involved
3. How the code and observability data correlate

Return a JSON object:
{"hypotheses": ["hypothesis 1", "hypothesis 2", ...], "needs_more_data": true/false, "next_focus": "optional hint for next search"}
"""

SYNTHESIZE_SYSTEM_PROMPT = """\
You are an expert SRE writing a root cause analysis report. Based on all \
gathered evidence and hypotheses, produce a clear, actionable RCA report.

Return a JSON object:
{
  "root_cause": "Clear explanation of the root cause",
  "confidence": 0.85,
  "evidence_summary": {
    "code": ["key code finding 1", ...],
    "logs": ["key log finding 1", ...],
    "metrics": ["key metric finding 1", ...],
    "traces": ["key trace finding 1", ...]
  }
}
"""


def _parse_time_range(time_range: str) -> int:
    """Convert time range string like '1h', '30m', '2h' to minutes."""
    time_range = time_range.strip().lower()
    if time_range.endswith("h"):
        return int(time_range[:-1]) * 60
    if time_range.endswith("m"):
        return int(time_range[:-1])
    if time_range.endswith("d"):
        return int(time_range[:-1]) * 1440
    return 60


def _build_evidence_context(state: RCAState) -> str:
    """Build a text summary of all evidence gathered so far."""
    parts = []
    if state.get("code_context"):
        parts.append(f"## Code Context ({len(state['code_context'])} chunks)")
        for c in state["code_context"][:10]:
            parts.append(f"- {c.get('file_path', '?')} ({c.get('service_name', '?')}): {c.get('content', '')[:200]}")

    if state.get("log_findings"):
        parts.append(f"\n## Log Findings ({len(state['log_findings'])} entries)")
        for log in state["log_findings"][:15]:
            parts.append(f"- [{log.get('timestamp', '')}] {log.get('line', '')[:200]}")

    if state.get("metric_findings"):
        parts.append(f"\n## Metric Findings ({len(state['metric_findings'])} series)")
        for m in state["metric_findings"][:10]:
            parts.append(f"- {m.get('metric', {})}: latest={m.get('latest_value')}")

    if state.get("trace_findings"):
        parts.append(f"\n## Trace Findings ({len(state['trace_findings'])} traces)")
        for t in state["trace_findings"][:10]:
            parts.append(
                f"- {t.get('root_service', '?')} {t.get('root_endpoint', '?')} "
                f"duration={t.get('duration_ms', 0)}ms spans={t.get('span_count', 0)}"
            )

    if state.get("hypotheses"):
        parts.append("\n## Current Hypotheses")
        for h in state["hypotheses"]:
            parts.append(f"- {h}")

    return "\n".join(parts) if parts else "No evidence gathered yet."


def _build_llm_invoke_config(state: RCAState, stage: str) -> dict:
    """Build LangChain invoke config with trace metadata for this RCA stage."""
    tags = [*state.get("trace_tags", []), "langgraph", "rca", stage]
    service = state.get("service")
    if service:
        tags.append(service)

    metadata = {
        "question": state.get("question", ""),
        "service": service or "",
        "time_range": state.get("time_range", "1h"),
        "iteration": state.get("iteration", 0) + 1,
        "stage": stage,
    }

    return build_langchain_config(
        session_id=state.get("session_id"),
        user_id=state.get("user_id"),
        tags=tags,
        metadata=metadata,
    )


async def plan_search(state: RCAState) -> dict:
    """LLM decides which tools to call based on the question and evidence so far."""
    llm = get_chat_llm()
    evidence = _build_evidence_context(state)
    lookback = _parse_time_range(state.get("time_range", "1h"))

    user_msg = (
        f"Question: {state['question']}\n"
        f"Service: {state.get('service') or 'not specified'}\n"
        f"Time range: {state.get('time_range', '1h')} ({lookback} minutes)\n"
        f"Iteration: {state.get('iteration', 0) + 1}/{state.get('max_iterations', 8)}\n\n"
        f"Evidence gathered so far:\n{evidence}"
    )

    resp = await llm.ainvoke(
        [
            HumanMessage(content=PLAN_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ],
        config=_build_llm_invoke_config(state, "plan_search"),
    )

    try:
        content = resp.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        plan = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse plan, defaulting to code search")
        plan = {"tools": [
            {"name": "search_code_vectors", "args": {
                "query": state["question"],
                "service_filter": state.get("service"),
            }},
        ], "ready": False}

    return {
        "current_step": "plan_search",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=f"Plan (iter {state.get('iteration', 0) + 1}): {json.dumps(plan)}")],
        "_plan": plan,
    }


async def execute_tools(state: RCAState) -> dict:
    """Execute the tools decided by plan_search."""
    from agent.tools.code_search import search_code_vectors
    from agent.tools.jaeger import query_jaeger_traces
    from agent.tools.opensearch import query_opensearch_logs
    from agent.tools.prometheus import query_prometheus_metrics

    tool_map = {
        "search_code_vectors": search_code_vectors,
        "query_opensearch_logs": query_opensearch_logs,
        "query_prometheus_metrics": query_prometheus_metrics,
        "query_jaeger_traces": query_jaeger_traces,
    }

    result_key_map = {
        "search_code_vectors": "code_context",
        "query_opensearch_logs": "log_findings",
        "query_prometheus_metrics": "metric_findings",
        "query_jaeger_traces": "trace_findings",
    }

    plan = state.get("_plan", {})
    tool_calls = plan.get("tools", [])

    updates: dict = {
        "current_step": "execute_tools",
        "code_context": [],
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "messages": [],
    }

    for call in tool_calls:
        name = call.get("name", "")
        args = call.get("args", {})
        fn = tool_map.get(name)
        if not fn:
            logger.warning("Unknown tool: %s", name)
            continue

        try:
            result = await fn.ainvoke(args)
            key = result_key_map[name]
            if isinstance(result, list):
                updates[key] = result
            else:
                updates[key] = [result] if result else []
            updates["messages"].append(
                AIMessage(content=f"Tool {name}: {len(updates[key])} results")
            )
            logger.info("Tool %s returned %d results", name, len(updates[key]))
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            updates["messages"].append(AIMessage(content=f"Tool {name} failed: {e}"))

    return updates


async def correlate_findings(state: RCAState) -> dict:
    """LLM analyzes all evidence and produces hypotheses."""
    llm = get_chat_llm()
    evidence = _build_evidence_context(state)

    resp = await llm.ainvoke(
        [
            HumanMessage(content=CORRELATE_SYSTEM_PROMPT),
            HumanMessage(content=f"Question: {state['question']}\n\n{evidence}"),
        ],
        config=_build_llm_invoke_config(state, "correlate_findings"),
    )

    try:
        content = resp.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        analysis = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        analysis = {"hypotheses": [resp.content[:500]], "needs_more_data": False}

    return {
        "current_step": "correlate",
        "hypotheses": analysis.get("hypotheses", []),
        "messages": [AIMessage(content=f"Correlation: {json.dumps(analysis)}")],
        "_needs_more_data": analysis.get("needs_more_data", False),
    }


def should_continue(state: RCAState) -> str:
    """Decide whether to loop back to plan_search or move to synthesis."""
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 8)

    if iteration >= max_iter:
        logger.info("Max iterations reached (%d), synthesizing", max_iter)
        return "synthesize"

    needs_more = state.get("_needs_more_data", False)
    plan = state.get("_plan", {})
    ready = plan.get("ready", False)

    if ready or not needs_more:
        return "synthesize"

    return "continue"


async def synthesize_root_cause(state: RCAState) -> dict:
    """Final LLM call to produce the RCA report."""
    llm = get_chat_llm()
    evidence = _build_evidence_context(state)

    resp = await llm.ainvoke(
        [
            HumanMessage(content=SYNTHESIZE_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Question: {state['question']}\n"
                f"Service: {state.get('service') or 'not specified'}\n\n"
                f"{evidence}"
            )),
        ],
        config=_build_llm_invoke_config(state, "synthesize_root_cause"),
    )

    try:
        content = resp.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        report = json.loads(content.strip())
    except (json.JSONDecodeError, IndexError):
        report = {
            "root_cause": resp.content,
            "confidence": 0.5,
            "evidence_summary": {},
        }

    return {
        "current_step": "done",
        "root_cause": report.get("root_cause", ""),
        "confidence": report.get("confidence", 0.5),
        "evidence_summary": report.get("evidence_summary", {}),
        "messages": [AIMessage(content=f"RCA complete: {report.get('root_cause', '')[:200]}")],
    }
