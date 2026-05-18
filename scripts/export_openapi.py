"""Export a static OpenAPI snapshot and a simple Swagger UI page."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from fastapi import FastAPI


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DOCS_DIR = ROOT / "docs"


def _install_stubs() -> None:
    """Stub runtime-only modules so router imports can succeed."""
    agent_pkg = types.ModuleType("agent")
    agent_graph = types.ModuleType("agent.graph")
    agent_graph.rca_agent = object()
    agent_tools_pkg = types.ModuleType("agent.tools")
    code_search = types.ModuleType("agent.tools.code_search")
    code_search.search_code_vectors = object()

    sys.modules.setdefault("agent", agent_pkg)
    sys.modules["agent.graph"] = agent_graph
    sys.modules["agent.tools"] = agent_tools_pkg
    sys.modules["agent.tools.code_search"] = code_search


def _build_app() -> FastAPI:
    sys.path.insert(0, str(BACKEND_DIR))
    _install_stubs()

    from routers.ingest import router as ingest_router
    from routers.query import router as query_router

    app = FastAPI(title="RAG Backend", version="0.2.0")
    app.include_router(ingest_router)
    app.include_router(query_router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


def _write_swagger_html(target: Path) -> None:
    target.write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RAG Backend Swagger UI</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: "./openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    </script>
  </body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    app = _build_app()
    spec = app.openapi()

    openapi_path = DOCS_DIR / "openapi.json"
    swagger_path = DOCS_DIR / "swagger.html"

    openapi_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    _write_swagger_html(swagger_path)

    print(f"Wrote {openapi_path}")
    print(f"Wrote {swagger_path}")


if __name__ == "__main__":
    main()
