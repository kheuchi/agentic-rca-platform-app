"""Shared RCA helpers used by the API and Chainlit UI."""


def build_initial_state(
    *,
    question: str,
    service: str | None = None,
    time_range: str = "1h",
    session_id: str | None = None,
    user_id: str | None = None,
    trace_tags: list[str] | None = None,
) -> dict:
    """Create the initial LangGraph state for an RCA run."""
    return {
        "question": question,
        "service": service,
        "time_range": time_range,
        "code_context": [],
        "log_findings": [],
        "metric_findings": [],
        "trace_findings": [],
        "hypotheses": [],
        "current_step": "start",
        "iteration": 0,
        "max_iterations": 8,
        "root_cause": "",
        "confidence": 0.0,
        "evidence_summary": {},
        "messages": [],
        "session_id": session_id,
        "user_id": user_id,
        "trace_tags": list(trace_tags or []),
    }


def build_rca_response(result: dict) -> dict:
    """Normalize the public RCA response shape."""
    return {
        "root_cause": result.get("root_cause", ""),
        "confidence": result.get("confidence", 0.0),
        "evidence": result.get("evidence_summary", {}),
        "iterations": result.get("iteration", 0),
        "hypotheses": result.get("hypotheses", []),
    }


def build_stream_payload(node_name: str, update: dict) -> dict:
    """Normalize a single streamed LangGraph node update."""
    payload = {
        "node": node_name,
        "step": update.get("current_step", node_name),
        "iteration": update.get("iteration"),
    }

    if node_name == "synthesize_root_cause":
        payload["root_cause"] = update.get("root_cause", "")
        payload["confidence"] = update.get("confidence", 0.0)
        payload["evidence"] = update.get("evidence_summary", {})

    return payload
