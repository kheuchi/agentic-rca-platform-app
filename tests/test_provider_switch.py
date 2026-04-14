import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


config_module = types.ModuleType("config")
config_module.settings = types.SimpleNamespace(
    azure_openai_endpoint="https://example.azure.com",
    azure_openai_api_key="secret",
    azure_openai_chat_deployment="gpt-4o",
    azure_openai_embedding_deployment="text-embedding-3-small",
    gcp_project_id="demo-project",
    gcp_location="us-central1",
    llm_provider_strategy="fallback",
    llm_switch_provider="azure",
    embedding_provider_strategy="fallback",
    embedding_switch_provider="azure",
)
sys.modules["config"] = config_module

llm_package = types.ModuleType("llm")
llm_tracing = types.ModuleType("llm.tracing")
llm_tracing.get_langfuse_handler = lambda: None
sys.modules["llm"] = llm_package
sys.modules["llm.tracing"] = llm_tracing

llama_index_package = types.ModuleType("llama_index")
llama_index_core = types.ModuleType("llama_index.core")
llama_index_schema = types.ModuleType("llama_index.core.schema")
llama_index_schema.TextNode = type("TextNode", (), {})
sys.modules["llama_index"] = llama_index_package
sys.modules["llama_index.core"] = llama_index_core
sys.modules["llama_index.core.schema"] = llama_index_schema


def load_module(name: str, path: pathlib.Path, extra_path: pathlib.Path):
    sys.path.insert(0, str(extra_path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


backend_providers = load_module(
    "backend_llm_providers",
    ROOT / "backend" / "llm" / "providers.py",
    ROOT / "backend",
)
backend_embeddings = load_module(
    "backend_llm_embeddings",
    ROOT / "backend" / "llm" / "embeddings.py",
    ROOT / "backend",
)
worker_embeddings = load_module(
    "worker_pipeline_embed",
    ROOT / "worker" / "pipeline" / "embed.py",
    ROOT / "worker",
)


class ProviderSwitchTests(unittest.TestCase):
    def test_chat_switch_can_force_azure(self):
        mode = backend_providers.resolve_chat_provider_mode(
            "switch",
            "azure",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "azure")

    def test_chat_switch_can_force_vertex(self):
        mode = backend_providers.resolve_chat_provider_mode(
            "switch",
            "vertex",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "vertex")

    def test_backend_embedding_switch_can_force_azure(self):
        mode = backend_embeddings.resolve_embedding_provider_mode(
            "switch",
            "azure",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "azure")

    def test_backend_embedding_switch_can_force_vertex(self):
        mode = backend_embeddings.resolve_embedding_provider_mode(
            "switch",
            "vertex",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "vertex")

    def test_worker_embedding_switch_can_force_azure(self):
        mode = worker_embeddings.resolve_embedding_provider_mode(
            "switch",
            "azure",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "azure")

    def test_worker_embedding_switch_can_force_vertex(self):
        mode = worker_embeddings.resolve_embedding_provider_mode(
            "switch",
            "vertex",
            azure_ready=True,
            vertex_ready=True,
        )
        self.assertEqual(mode, "vertex")


if __name__ == "__main__":
    unittest.main()
