import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


rca_helpers = load_module("backend_agent_rca", ROOT / "backend" / "agent" / "rca.py")


class RCAHelpersTests(unittest.TestCase):
    def test_build_initial_state_keeps_trace_context(self):
        state = rca_helpers.build_initial_state(
            question="Why is frontendproxy failing?",
            service="frontendproxy",
            time_range="30m",
            session_id="sess-123",
            user_id="user-456",
            trace_tags=["chainlit", "rca-ui"],
        )

        self.assertEqual(state["question"], "Why is frontendproxy failing?")
        self.assertEqual(state["service"], "frontendproxy")
        self.assertEqual(state["time_range"], "30m")
        self.assertEqual(state["session_id"], "sess-123")
        self.assertEqual(state["user_id"], "user-456")
        self.assertEqual(state["trace_tags"], ["chainlit", "rca-ui"])

    def test_build_rca_response_normalizes_result(self):
        response = rca_helpers.build_rca_response(
            {
                "root_cause": "Timeouts on backend dependency",
                "confidence": 0.81,
                "evidence_summary": {"logs": ["timeout"]},
                "iteration": 3,
                "hypotheses": ["dependency timeout"],
            }
        )

        self.assertEqual(response["root_cause"], "Timeouts on backend dependency")
        self.assertEqual(response["confidence"], 0.81)
        self.assertEqual(response["evidence"], {"logs": ["timeout"]})
        self.assertEqual(response["iterations"], 3)
        self.assertEqual(response["hypotheses"], ["dependency timeout"])

    def test_build_stream_payload_adds_final_fields_for_synthesis(self):
        payload = rca_helpers.build_stream_payload(
            "synthesize_root_cause",
            {
                "current_step": "done",
                "iteration": 2,
                "root_cause": "Checkout retries saturated the service",
                "confidence": 0.78,
                "evidence_summary": {"metrics": ["high latency"]},
            },
        )

        self.assertEqual(payload["node"], "synthesize_root_cause")
        self.assertEqual(payload["step"], "done")
        self.assertEqual(payload["iteration"], 2)
        self.assertEqual(payload["root_cause"], "Checkout retries saturated the service")
        self.assertEqual(payload["confidence"], 0.78)
        self.assertEqual(payload["evidence"], {"metrics": ["high latency"]})


if __name__ == "__main__":
    unittest.main()
