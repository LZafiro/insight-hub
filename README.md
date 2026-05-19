# Insight Hub

An AI-powered research assistant that lets teams query a corpus of internal documents and get answers grounded in **verifiable citations**. Built as a portfolio project demonstrating production-grade patterns for RAG, multi-tenant SaaS, and AWS deployment.

> **Status:** Work in progress. See [roadmap](#roadmap).

## Demo

_[Add screenshot/GIF or deployed URL here]_

## Problem

Knowledge workers spend hours hunting through past reports, decks, and memos for information they know exists "somewhere". Generic LLM chat tools hallucinate and can't be trusted with proprietary content. Insight Hub provides a private, citation-grounded Q&A layer over an organization's document corpus.

## Architecture

```
┌─────────────┐   JWT    ┌──────────────────┐
│  Next.js    │ ───────▶ │  FastAPI (ECS)   │
│  Frontend   │          └────────┬─────────┘
└─────────────┘                   │
                                  ├──▶ Postgres + pgvector  (metadata + embeddings)
                                  ├──▶ Redis                (cache, sessions, rate limit)
                                  ├──▶ S3                   (raw documents)
                                  └──▶ LLM provider         (OpenAI / Anthropic)
                                  ▲
                                  │
                          ┌───────┴────────┐
                          │ Ingestion       │
                          │ worker (async)  │
                          └─────────────────┘
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for detailed decisions and trade-offs.

## Stack

| Layer       | Choice                          | Why                                                                 |
|-------------|---------------------------------|---------------------------------------------------------------------|
| Backend     | FastAPI + Python 3.12           | Async-first, great DX, type-safe                                    |
| ORM         | SQLAlchemy 2.0 (async)          | Industry standard, full async support                               |
| Vector DB   | Postgres + pgvector             | One less moving part; sufficient for <1M chunks                     |
| Cache       | Redis                           | Cache expensive embedding lookups + rate limiting                   |
| Auth        | OAuth 2.0 (PKCE) + JWT          | Industry-standard, stateless                                        |
| Frontend    | Next.js 14 (App Router) + TS    | Modern React, server components, type-safe                          |
| Infra       | AWS ECS Fargate + RDS           | No EC2 ops; managed; cost-effective at this scale                   |
| IaC         | Terraform                       | Declarative, portable                                               |
| CI/CD       | GitHub Actions                  | Native to the repo                                                  |

## Running locally

Prerequisites: Docker, Python 3.12, Node 20, `uv` (or pip).

```bash
# 1. Copy env template
cp .env.example .env
# Edit .env with your OpenAI/Anthropic API key

# 2. Spin up Postgres + Redis + backend
docker compose up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. (Optional) Seed sample data
docker compose exec backend python -m scripts.seed_data

# 5. Frontend
cd frontend && npm install && npm run dev
```

API at `http://localhost:8000`, docs at `http://localhost:8000/docs`, frontend at `http://localhost:3000`.

## Testing

```bash
cd backend
uv run pytest                    # run all tests
uv run pytest --cov=app          # with coverage
uv run ruff check .              # lint
uv run mypy app                  # type-check
```

## Project structure

```
backend/app/
├── api/         HTTP layer (routers, deps)
├── core/        cross-cutting: config, db, security, logging
├── domain/      data models & Pydantic schemas
├── services/    business logic (RAG, ingestion, LLM)
├── repositories/ data access (decouples ORM from services)
└── workers/     async background jobs
```

The split between `services/` and `repositories/` is deliberate: services orchestrate business logic and never touch SQLAlchemy directly. This keeps tests fast (mock repos) and the swap of a data store cheap.

## Trade-offs

Explicit decisions worth defending in a review:

- **pgvector over Pinecone**: Eliminates a dependency. For >10M chunks I'd migrate to a dedicated vector DB (Pinecone, Weaviate, or Qdrant). Below that threshold the latency is equivalent and the operational simplicity wins.
- **Single Postgres for all relational + vector data**: Simpler ops. If the embedding workload grew, I'd split into a dedicated vector instance to isolate vacuum/IO pressure.
- **JWT (stateless) over server sessions**: Easier to scale horizontally. Trade-off: revocation requires a denylist in Redis, which is implemented for high-privilege tokens only.
- **Synchronous ingestion in MVP, async worker in v2**: Shipped a working flow first; moved to background processing once chunk counts grew. Worker uses SQS in production, in-process queue in dev.
- **LLM provider as injected dependency**: Swappable between OpenAI/Anthropic/local via `LLMProvider` protocol. Useful for A/B testing models and reducing vendor lock-in.

## Roadmap

- [x] Project scaffolding, CI, Docker
- [x] Auth (OAuth + JWT)
- [x] Document ingestion + RAG pipeline
- [ ] Multi-tenant workspaces + RBAC
- [ ] Streaming responses (SSE)
- [ ] Observability: structured logging, metrics, cost tracking
- [ ] AWS deployment via Terraform
- [ ] Eval harness (RAGAS)
- [ ] Guardrails: PII redaction, prompt injection detection

## What I'd do with more time

- Hybrid retrieval (BM25 + dense) with cross-encoder re-ranking
- LLM-as-judge eval pipeline running in CI on a golden dataset
- Per-workspace fine-tuned embeddings
- Audit log to an append-only store (e.g., DynamoDB) for compliance
- Cost dashboard per workspace/user

## License

MIT
# insight-hub
