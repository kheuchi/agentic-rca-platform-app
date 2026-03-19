"""RCA agent state definition for LangGraph."""

from typing import TypedDict

from langchain_core.messages import BaseMessage


class RCAState(TypedDict):
    """State carried through the LangGraph RCA agent."""

    question: str
    service: str | None
    time_range: str

    # Accumulated evidence
    code_context: list[dict]
    log_findings: list[dict]
    metric_findings: list[dict]
    trace_findings: list[dict]

    # Reasoning
    hypotheses: list[str]
    current_step: str
    iteration: int
    max_iterations: int

    # Output
    root_cause: str
    confidence: float
    evidence_summary: dict
    messages: list[BaseMessage]
