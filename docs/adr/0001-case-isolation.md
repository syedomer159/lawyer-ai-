# ADR-0001: One SQLite database and folder per case

- Status: accepted
- Date: 2026-10-20

## Context
Case material is confidential, and mixing two clients' material would be a serious breach. Legal-AI practice treats the matter as a hard security boundary rather than a metadata filter, and when unsure it fails closed. The MVP is single-user, and one case has hundreds to a few thousand chunks.

## Decision
- Each case gets `data/cases/<case_id>/case.db` (documents, pages, chunks + FTS5, embeddings as BLOBs, claims, conflicts, gaps, issues, trial sessions, jobs) and `files/` (uploads, rendered page images).
- `data/registry.db` holds only the list of cases.
- Each request opens exactly one case store. Retrieval and agent tools receive that store and nothing else. There is no global index, cache or memory.
- Vector search is numpy cosine over that one case's embeddings, fused with FTS5 BM25 via reciprocal rank fusion. There is no vector DB.
- Deleting a case deletes its folder.

## Consequences
- Leaking content across cases needs a code path that opens two stores, so the isolation test checks exactly that.
- No extra infrastructure; backup is copying a folder.
- Cross-case features (firm-wide search) are deliberately impossible without a new ADR.
- Not encrypted at rest yet (next step: SQLCipher or disk encryption).

## Alternatives considered
- Postgres + pgvector with a `case_id` row filter: the isolation is only a WHERE clause, and it adds a service to run.
- Chroma/Qdrant collection per case: an extra service with no gain at this size.
