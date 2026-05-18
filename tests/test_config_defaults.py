import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConfigDefaultsTests(unittest.TestCase):
    def test_backend_defaults_keep_rag_dev_on_azure_switch(self):
        content = (ROOT / "backend" / "config.py").read_text(encoding="utf-8")
        self.assertIn('llm_provider_strategy: str = "switch"', content)
        self.assertIn('llm_switch_provider: str = "azure"', content)
        self.assertIn('embedding_provider_strategy: str = "switch"', content)
        self.assertIn('embedding_switch_provider: str = "azure"', content)

    def test_worker_defaults_keep_embeddings_on_azure_switch(self):
        content = (ROOT / "worker" / "config.py").read_text(encoding="utf-8")
        self.assertIn('embedding_provider_strategy: str = "switch"', content)
        self.assertIn('embedding_switch_provider: str = "azure"', content)


if __name__ == "__main__":
    unittest.main()
