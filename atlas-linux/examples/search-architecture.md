# Search architecture

The search pipeline has three stages: document ingestion, retrieval, and evidence inspection. RAGFlow owns parsing and semantic retrieval. Atlas owns the application experience and a normalized graph model.

## RAGFlow

RAGFlow splits documents into chunks, builds embeddings, and retrieves relevant content. Configure an embedding model and a chat model in the RAGFlow server before building a knowledge graph. Knowledge compilation and graph APIs vary by server release.

[[RAGFlow]] --supports--> [[Knowledge discovery]]
[[Project Atlas]] --stores metadata in--> [[PostgreSQL]]

## Source evidence

When someone searches for "Who leads Atlas?", show the relevant source excerpt and allow them to open the document. Local mode uses keyword retrieval and returns excerpts. It does not generate answers or use embeddings.

## Knowledge discovery

A document-topic graph is a useful map of content. An entity graph goes further: it says who owns a project or which technology a project depends on. Similarity alone is not enough evidence to claim a relationship.
