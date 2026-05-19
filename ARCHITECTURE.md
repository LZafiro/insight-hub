# Architecture

This document captures the design decisions for Insight Hub and the reasoning behind them. Decisions are listed roughly in order of impact.

## 1. Layered backend

The backend is organized in four layers, each depending only on the layer below:

```
api/          → HTTP handlers, request/response shaping
services/     → business logic, orchestration, domain rules
repositories/ → data access (SQLAlchemy lives here only)
core/         → cross-cutting (config, db, security, logging)
```

**Why:** Tests for services don't need a database — repos are mocked at the protocol boundary. Swapping the ORM or vector store touches one layer only. The cost is some boilerplate.

## 2. RAG pipeline

```
Document ──▶ Parser ──▶ Chunker ──▶ Embedder ──▶ pgvector
                                                    │
Query ──▶ Embedder ──▶ Retriever ──▶ Re-ranker ─────┤
                                       │            │
                                       ▼            │
                                  Prompt builder ◀──┘
                                       │
                                       ▼
                                  LLM ──▶ Response with citations
```

**Chunking strategy:** Recursive character splitter with overlap. Tuned per content type (a deck has different ideal chunk size than a memo). Configurable per workspace.

**Citations:** Every chunk retrieved gets a stable ID; the prompt instructs the LLM to cite via `[chunk_id]`. The frontend resolves these to source links at render time. The LLM is also instructed to refuse to answer if no relevant chunks are retrieved (`top_k_score < threshold`).

**Embeddings cache:** Embedding the same query twice is waste; Redis caches `query_hash → vector` with a 24h TTL. Cache hit rate ≈40% in typical usage.

## 3. Multi-tenancy

Tenancy unit: `Workspace`. All data tables include a `workspace_id` column. A row-level security policy (Postgres RLS) enforces isolation — the application-layer JWT carries the workspace_id, set on every connection via `SET app.workspace_id = ...`.

**Why RLS:** Defense in depth. Even an SQL injection or developer mistake can't leak across workspaces.

## 4. Auth

OAuth 2.0 authorization code flow with PKCE. JWT for session tokens (15min access, 7d refresh). Refresh tokens are stored in an HttpOnly cookie; access tokens live in memory on the frontend.

**Revocation:** Access tokens are short-lived enough that immediate revocation isn't critical. Refresh tokens can be revoked via a Redis denylist keyed by `jti`.

## 5. Observability

- **Logging:** Structured JSON via `structlog`. Every request gets a correlation ID propagated through async tasks.
- **Metrics:** Prometheus format on `/metrics`. Custom metrics: `llm_tokens_total{model,workspace}`, `llm_latency_seconds`, `rag_retrieval_score`.
- **Tracing:** OpenTelemetry-ready; spans for retrieval, embedding, LLM call.
- **Cost tracking:** Each LLM call records `(input_tokens, output_tokens, model)` to a `usage_events` table. Aggregated nightly for cost-per-workspace reporting.

## 6. Deployment topology

```
Route 53 ──▶ CloudFront ──▶ ALB ──▶ ECS Fargate (FastAPI)
                                       │
                                       ├──▶ RDS Postgres (Multi-AZ in prod)
                                       ├──▶ ElastiCache Redis
                                       ├──▶ S3 (documents bucket, KMS-encrypted)
                                       └──▶ Secrets Manager
```

Frontend deployed as static export to S3 + CloudFront. Worker is a separate ECS service consuming from SQS.

## 7. Things deliberately out of scope (and why)

- **Real-time collaboration on docs:** Out of MVP scope; the product is read-mostly.
- **Self-hosted LLM:** Vendor APIs are 10x faster to MVP and the cost difference doesn't matter at portfolio scale.
- **Mobile app:** Web works fine.
- **Document editing:** Read-only ingestion only.
