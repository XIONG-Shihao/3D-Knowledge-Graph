# Atlas product specification

MVP snapshot: 2026-10-08. This document separates shipped behavior from proposed work. See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation and [the Linux guide](../deploy/LINUX.md) for setup.

## 1. Purpose

Help a user turn scattered Chinese and English documents into an organized, searchable knowledge base, then explore connections and inspect the original evidence.

The two user outcomes are:

1. **Organize knowledge:** group documents by project, inspect extracted chunks and topics, and find relevant passages.
2. **Visualize knowledge:** see documents, topics and supplied entity relationships, then follow a connection back to its source.

The initial user is a researcher or project owner working privately. The application is designed for one operator; company-wide sharing and multiple-user permissions are future work.

## 2. Practical example

A project owner uploads `中文项目说明.md` containing:

```text
# 知识图谱项目
[[张伟]] --负责--> [[知识图谱项目]]
项目的目标是整理内部技术文档，并展示知识之间的关系。
```

Atlas extracts readable chunks and topics. Searching `知识图谱` finds matching excerpts. In the graph, selecting the `负责` connection opens the source document and its annotation chunk.

This provides an understandable relationship with evidence. An ordinary mention of two people in the same paragraph does not automatically mean they work together.

## 3. Main user journey

| Step | User action | Result |
|---|---|---|
| Create | Name a knowledge base and choose Local or RAGFlow | A separate project workspace |
| Add sources | Upload supported files | Visible processing state, progress where available, and actionable errors |
| Inspect | Open a document or topic | Extracted chunks, local PDF pages, topic membership and available original downloads |
| Find | Search Chinese or English text | Relevant source excerpts scoped to the selected knowledge base |
| Explore | Filter the graph and select a node/edge | Relationship details, origin and available source links |
| Maintain | Retry failed files, refresh RAGFlow or delete documents | Updated content and graph state |

Local mode is the fastest first-run path: it needs no external service or model credentials. RAGFlow adds remote parsing and semantic retrieval once its service and models are configured.

## 4. Shipped capabilities

| Capability | Local engine | RAGFlow engine / import |
|---|---|---|
| Knowledge-base organization | Separate projects stored locally | Local workspace mapped to a remote dataset |
| Atlas upload formats | Markdown, TXT, text PDF, DOCX; 20 MiB/file | Same Atlas upload gate; forwarded for remote parsing |
| Chunk inspection | Parsed text; page numbers for local PDFs | Synced remote chunks; document/chunk references |
| Topics | Headings, `[[references]]`, frequent keywords | Topics derived from synced content/keywords |
| Search | BM25-style lexical ranking; Chinese bigrams | RAGFlow retrieval; semantic Chinese matching needs a suitable embedding model |
| Graph | Documents/topics plus explicit author relationships | JSON imports; optional legacy RAGFlow build/fetch |
| Graph visualization | 2D Cytoscape explorer | Same 2D explorer for normalized remote/imported graphs |
| Source inspection | Original uploads and annotation chunks | Resolved synced sources; unresolved references remain visible |
| Language | Simplified Chinese default; English switch | Same interface; source language unchanged |
| Persistence | SQLite and original files | Atlas metadata/cache plus independent RAGFlow storage |

Graph JSON import/export supports exchanging relationship data. Imports replace the displayed graph; returning to the document/topic map restores the locally generated view. The import limits are 5 MiB, 2,000 nodes and 5,000 edges.

## 5. Graph meaning and trust

Users must be able to distinguish structure from a factual relationship:

- **Document → covers → topic:** the document contains that topic.
- **张伟 → 负责 → 知识图谱项目:** a supplied annotation or imported graph explicitly states this relationship.
- **Source link:** a reference resolves to a document/chunk in the selected knowledge base. It lets the user inspect evidence; it does not certify the statement as true.
- **Unresolved reference:** the input supplied a source ID that Atlas cannot match. Atlas retains the reference instead of inventing a citation.

The interface displays graph origin. Local mode does not infer semantic relationships from keyword co-occurrence. Imported or model-generated relationships need human inspection against their sources.

## 6. Does the knowledge graph support 3D?

**The current MVP displays graphs in 2D only. 3D is feasible but not shipped.** Graph data is independent of the renderer, so the same people, projects, relationships and evidence can be displayed in a 3D view without rebuilding the knowledge base.

A proposed 3D option would use a WebGL renderer such as [3d-force-graph](https://github.com/vasturiano/3d-force-graph), with rotation, zoom and node/edge selection connected to the existing source inspector. A 2D/3D switch would preserve the selected knowledge base and filters. Labels, performance and accessibility must be validated before release.

The [3D proposal](3D_PROPOSAL.md) adopts nodes/connections in 3D with flat, upright labels facing the screen. Chinese text remains readable as the camera rotates. Label overlap is handled separately through priorities, offsets and a visibility budget. This is a proposed design, not a shipped feature.

**Recommendation: keep 2D as the default and make 3D optional.** 2D is easier for reading Chinese names, following labeled relationships and checking source passages. 3D is useful for exploring the overall shape of a collection, but camera motion and overlapping labels can make precise reading harder. Depth does not add new knowledge: the relationship `张伟负责知识图谱项目` stays the same in either view.

## 7. Chinese experience

The interface starts in Simplified Chinese; language switching persists in the browser. Uploaded content, filenames and graph labels retain their original language. Local search supports Chinese character bigrams and highlights matched Chinese terms. UTF-8, UTF-16 with a BOM, and GB18030 text files are accepted.

Chinese interface support and Chinese semantic retrieval are different capabilities. Local keyword search works without a model; RAGFlow semantic search depends on the embedding model selected in that service. Mixed Chinese/English documents can stay in the same knowledge base.

## 8. Deployment and the RAGFlow connection

The deliverable supports Mac development and prepares a **native Ubuntu 24.04 x86_64 deployment without Docker**, including Atlas and a pinned RAGFlow service profile. The Linux package contains the compiled Atlas interface, dependency locks, scripts, examples and documentation.

Think of Atlas as the workspace and RAGFlow as a separate processing engine. “Connect RAGFlow” means:

1. Install the native services using [deploy/LINUX.md](../deploy/LINUX.md).
2. Open the RAGFlow management interface, configure Chinese-capable embedding and required chat models, and create an account API key.
3. Put the RAGFlow API address and that account key in Atlas's backend environment, then restart Atlas.
4. Choose the RAGFlow engine when creating a knowledge base; upload, refresh and test a small document.

Atlas uses port 8000, RAGFlow's management interface uses 8080, and Atlas connects to the RAGFlow API on 9380. Browser access to Linux uses SSH forwarding. The connection badge means settings exist; it does not prove that the service, credentials or parsing work.

The native RAGFlow profile pins v0.22.1 for compatibility. Full native installation and document processing still require verification on the destination Linux host. Installing the profile does not install an embedding/chat model server or configure model-provider credentials automatically.

## 9. MVP boundaries

The following are not shipped:

- Multiple users, login, organizational permissions or public shared deployment.
- Generated chat answers, local embeddings, local OCR or automatic local AI entity extraction.
- A 3D renderer or persistent graph layout coordinates.
- Automation for every newer RAGFlow knowledge-compilation artifact API.
- Custom RAGFlow ingestion pipelines, incremental sync or durable Atlas processing jobs.
- Preservation of DOCX images, footnotes and page layout.

Retrieval returns excerpts. A scanned PDF without readable text fails in local mode and needs OCR through an appropriate remote configuration. Documents synced from RAGFlow may lack a local original download. Separate knowledge bases organize content; they do not enforce access controls.

## 10. Acceptance checklist

Use this checklist on a fresh installation. These are acceptance requirements, not a claim that the complete native Linux stack has already passed them.

| Scenario | Expected outcome |
|---|---|
| Launch local mode without RAGFlow credentials | App opens, supported files process, and local search/graph work |
| Upload the Chinese example | Chinese text remains readable; searching `知识图谱` returns matching excerpts |
| Inspect the explicit `负责` edge | Correct source document and annotation chunk are available |
| Switch Chinese/English and reload | Interface preference persists; content labels remain unchanged |
| Import graph JSON with an unknown source ID | Graph appears as imported; the source stays unresolved |
| Import duplicate IDs or a dangling edge | A validation error prevents storing an invalid graph |
| Delete a ready document | Its chunks and dependent generated graph content disappear |
| Restart Atlas | Existing data persists; interrupted queued local uploads can be retried |
| Install the native Linux stack | Service checks pass; a Chinese upload reaches ready state and live retrieval succeeds |
| Attach a RAGFlow dataset and refresh | Remote documents/chunks appear in the correct local workspace |

Existing tests exercise local workflows, Chinese search, graph/source validation, persistence, mocked remote contracts and deployment configuration. A live native RAGFlow install and configured models are necessary for the last two scenarios.

## 11. Next priorities

1. **Verify the Linux baseline:** complete native installation, model configuration and Chinese ingestion/retrieval on the target server; record actual results.
2. **Improve reliability:** durable processing jobs, incremental remote sync, backup/restore verification and useful error recovery.
3. **Prepare sharing if needed:** login and permissions enforced across upload, download, graph and retrieval paths before a shared rollout.
4. **Prototype optional 3D:** compare Chinese label readability, source inspection and performance against the current 2D view using real collections.

Measure whether users can find a passage, identify a useful relationship and open its supporting source. Record processing failures and retrieval relevance on a small representative Chinese/English corpus. Performance targets and usage analytics are not established in this MVP; collect a baseline before promising scale or ranking quality.
