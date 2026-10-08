# Product strategy

Atlas is a shared knowledge workspace for Acme Research. Its goal is to make decisions, technical documentation, and project knowledge easy to find. Alice Chen leads Project Atlas. The initial release focuses on document ingestion, evidence-backed search, and an interactive knowledge graph.

## Knowledge discovery

Users should be able to move from a topic to the documents behind it. Every relationship needs a source. We will measure success by whether a new teammate can find the owner, dependencies, and rationale for a project in under two minutes.

## Project Atlas

Project Atlas connects document storage with RAGFlow for parsing and semantic retrieval. PostgreSQL is planned for the production application database. The prototype uses SQLite for simplicity.

The following relationships are explicitly annotated by the author:

[[Alice Chen]] --leads--> [[Project Atlas]]
[[Project Atlas]] --belongs to--> [[Acme Research]]
[[Project Atlas]] --uses--> [[RAGFlow]]

## Release plan

The MVP is a single-user local workspace. A shared deployment will require sign-in, organization access checks, background workers, and audit logs. The production release must enforce permissions before retrieving any chunks.
