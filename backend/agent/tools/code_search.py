"""Code vector search tool — queries Azure AI Search for code chunks."""

# TODO Phase 4.3: Implement search_code_vectors tool
# - Input: query string, optional service_filter, top_k
# - Embed query via Azure OpenAI text-embedding-3-small
# - Hybrid search (vector + keyword) against Azure AI Search index "code-chunks"
# - Return list of code chunks with file_path, content, score
