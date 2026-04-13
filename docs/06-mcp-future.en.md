# Phase 6 - MCP (Model Context Protocol) - Future implementation

English version. Version francaise: [06-mcp-future.md](./06-mcp-future.md)

> Status: not implemented yet.

---

## What MCP is

Model Context Protocol is a standard way for LLM agents to access external tools and resources such as:
- filesystems
- git history
- GitHub APIs
- documentation systems

## Why RAG alone is not enough

RAG is excellent for semantic discovery, but it has structural limits:
- the index can become stale
- chunks can miss surrounding context
- there is no directory navigation
- there is no git blame or commit history
- rich documentation structure is flattened into text

## Target design: hybrid RAG + MCP

The intended Phase 6 design is:
- use RAG to find relevant code quickly
- use MCP to read full files, inspect nearby files, and consult git or docs

In short:
- RAG finds
- MCP reads

## Likely MCP servers

Planned candidates:
- filesystem
- git
- GitHub
- Confluence
- fetch

## Impact on the RCA agent

The LangGraph graph itself does not need a redesign.

The likely change is to extend the tool map with MCP-backed tools such as:
- `read_file`
- `git_blame`
- `get_confluence_page`

Existing observability tools would stay the same:
- Loki
- Prometheus
- Tempo

## Why MCP comes later

MCP is intentionally delayed because:
- the current RAG + RCA pipeline had to be stabilized first
- MCP is much easier to exploit with a conversational UI
- filesystem and git access need careful permission design
