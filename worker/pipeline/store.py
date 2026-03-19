"""Azure AI Search upsert step — store embedded chunks in vector index."""

# TODO Phase 4.2: Implement store_chunks(chunks)
# - Upsert into Azure AI Search index "code-chunks"
# - Key format: <repo_hash>:<file_hash>:<chunk_idx>
# - Include all metadata fields (file_path, service_name, language, etc.)
