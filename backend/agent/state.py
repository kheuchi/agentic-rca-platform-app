"""RCA agent state definition for LangGraph."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class RCAState(TypedDict):
    """State carried through the LangGraph RCA agent."""

    question: str
    service: str | None
    time_range: str

    # Accumulated evidence (reducers append instead of overwrite)
    code_context: Annotated[list[dict], operator.add]
    log_findings: Annotated[list[dict], operator.add]
    metric_findings: Annotated[list[dict], operator.add]
    trace_findings: Annotated[list[dict], operator.add]

    # Reasoning
    hypotheses: Annotated[list[str], operator.add]
    current_step: str
    iteration: int
    max_iterations: int

    # Output
    root_cause: str
    confidence: float
    evidence_summary: dict
    messages: Annotated[list[BaseMessage], add_messages]
