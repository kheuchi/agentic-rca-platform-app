"""Chainlit UI for the RCA agent."""

from __future__ import annotations

import hmac
import os
import pathlib
import sys

import chainlit as cl
from chainlit.input_widget import Select, Switch, TextInput

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.graph import rca_agent  # noqa: E402
from agent.rca import build_initial_state, build_stream_payload  # noqa: E402


DEFAULT_SETTINGS = {
    "service": "frontendproxy",
    "time_range": "1h",
    "show_steps": True,
    "show_evidence": True,
}


def _auth_enabled() -> bool:
    return bool(os.getenv("CHAINLIT_USERNAME") and os.getenv("CHAINLIT_PASSWORD"))


if _auth_enabled():

    @cl.password_auth_callback
    def auth_callback(username: str, password: str):
        expected_username = os.getenv("CHAINLIT_USERNAME")
        expected_password = os.getenv("CHAINLIT_PASSWORD")

        if hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password):
            return cl.User(identifier=username, metadata={"provider": "credentials", "role": "admin"})

        return None


def _get_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    settings.update(cl.user_session.get("settings") or {})
    return settings


def _set_settings(settings: dict) -> None:
    cl.user_session.set("settings", settings)


def _format_final_report(root_cause: str, confidence: float, evidence: dict, settings: dict) -> str:
    lines = [
        "## Root Cause",
        root_cause or "No root cause produced.",
        "",
        f"Confidence: `{confidence:.2f}`",
    ]

    if settings.get("show_evidence", True) and evidence:
        lines.extend(["", "## Evidence"])
        for label in ("code", "logs", "metrics", "traces"):
            items = evidence.get(label, [])
            if not items:
                continue
            lines.append(f"### {label.capitalize()}")
            for item in items:
                lines.append(f"- {item}")

    return "\n".join(lines)


@cl.on_chat_start
async def on_chat_start():
    settings = await cl.ChatSettings(
        [
            TextInput(
                id="service",
                label="Service filter",
                initial=DEFAULT_SETTINGS["service"],
                description="Leave empty to let the agent search across services.",
            ),
            Select(
                id="time_range",
                label="Time range",
                values=["15m", "30m", "1h", "2h", "6h"],
                initial_index=2,
            ),
            Switch(
                id="show_steps",
                label="Show intermediate RCA steps",
                initial=DEFAULT_SETTINGS["show_steps"],
            ),
            Switch(
                id="show_evidence",
                label="Show final evidence summary",
                initial=DEFAULT_SETTINGS["show_evidence"],
            ),
        ]
    ).send()

    _set_settings(settings)

    auth_notice = "\n\nAuthentication is enabled for this deployment." if _auth_enabled() else ""

    await cl.Message(
        content=(
            "RCA chat is ready.\n\n"
            "Ask a question such as `Why is frontendproxy failing to route requests?`\n\n"
            "Platform guardrail: `rag-dev` stays on Azure while the Vertex switch remains paused."
            f"{auth_notice}"
        )
    ).send()


@cl.on_settings_update
async def on_settings_update(settings):
    _set_settings(settings)


@cl.on_message
async def on_message(message: cl.Message):
    settings = _get_settings()
    service = (settings.get("service") or "").strip() or None
    time_range = settings.get("time_range", "1h")
    show_steps = bool(settings.get("show_steps", True))

    session_id = cl.user_session.get("id")
    user = cl.user_session.get("user")
    user_id = user.identifier if user else None

    initial_state = build_initial_state(
        question=message.content,
        service=service,
        time_range=time_range,
        session_id=session_id,
        user_id=user_id,
        trace_tags=["chainlit", "rca-ui"],
    )

    progress = await cl.Message(content="Running RCA agent...").send()
    progress_lines: list[str] = []
    final_payload: dict = {}

    try:
        async for event in rca_agent.astream(initial_state, stream_mode="updates"):
            for node_name, update in event.items():
                payload = build_stream_payload(node_name, update)
                if payload.get("root_cause"):
                    final_payload = payload

                if show_steps:
                    iteration = payload.get("iteration")
                    suffix = f" (iteration {iteration})" if iteration else ""
                    progress_lines.append(f"- `{payload['node']}`{suffix}")
                    progress.content = "Running RCA agent...\n\n" + "\n".join(progress_lines[-8:])
                    await progress.update()
    except Exception as exc:
        progress.content = f"RCA failed: `{exc}`"
        await progress.update()
        return

    if not final_payload:
        progress.content = "RCA finished without a final synthesis payload."
        await progress.update()
        return

    progress.content = "RCA run complete."
    await progress.update()

    await cl.Message(
        content=_format_final_report(
            final_payload.get("root_cause", ""),
            final_payload.get("confidence", 0.0),
            final_payload.get("evidence", {}),
            settings,
        )
    ).send()
