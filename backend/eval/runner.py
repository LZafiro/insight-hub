"""RAG evaluation pipeline.

Runs two stages:
  1. Traditional metrics — retrieval (hit rate, MRR, precision@k) and
     generation (answer presence, refusal rate, citation accuracy).
  2. LLM-as-a-judge — faithfulness, relevance, and correctness scored 1-5.

Usage:
    docker compose exec backend python -m eval.runner

Results are written to eval/results/eval_<timestamp>.json.
Exits with code 1 if any configured threshold is not met.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.domain.models import Workspace
from app.repositories.chunks import ChunkRepository
from app.services.embeddings import build_embedding_provider
from app.services.llm import LLMMessage, LLMProvider, build_llm_provider
from app.services.rag import SYSTEM_PROMPT
from app.services.reranker import CrossEncoderReranker
from app.services.retriever import HybridRetriever
from eval.judges.llm_judge import LLMJudge
from eval.metrics.generation import (
    answer_presence_rate,
    avg_citation_accuracy,
    refusal_rate_on_oos,
)
from eval.metrics.retrieval import hit_rate, mrr, precision_at_k

GOLDEN_SET_PATH = Path(__file__).parent / "dataset" / "golden_set.json"
RESULTS_DIR = Path(__file__).parent / "results"


async def _run_query(
    row: dict,
    retriever: HybridRetriever,
    reranker: CrossEncoderReranker,
    llm: LLMProvider,
    workspace_id: object,
) -> dict:
    query = row["query"]

    candidates = await retriever.retrieve(
        query, workspace_id, candidate_k=settings.retrieval_candidate_k
    )
    candidate_filenames = [c.document.filename for c in candidates if c.document]

    reranked = await reranker.rerank(query, candidates, top_k=settings.retrieval_top_k)
    reranked_filenames = [c.document.filename for c in reranked if c.document]

    if not reranked:
        answer = "I don't have enough information in the provided documents to answer that."
        context = ""
    else:
        excerpts = [f"[{i + 1}] {c.content}" for i, c in enumerate(reranked)]
        context = "\n\n".join(excerpts)
        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=f"Context excerpts:\n\n{context}\n\nQuestion: {query}"),
        ]
        response = await llm.complete(messages, temperature=0)
        answer = response.content

    return {
        "id": row["id"],
        "query": query,
        "relevant_documents": row["relevant_documents"],
        "reference_answer": row.get("reference_answer"),
        "candidate_filenames": candidate_filenames,
        "reranked_filenames": reranked_filenames,
        "num_reranked_chunks": len(reranked),
        "context": context,
        "answer": answer,
        "judge_scores": {},
    }


async def _run_judge(result: dict, judge: LLMJudge) -> dict:
    query = result["query"]
    answer = result["answer"]
    context = result["context"]
    reference = result["reference_answer"]

    if not result["relevant_documents"]:
        return result

    faith = await judge.faithfulness(query, context, answer)
    rel = await judge.relevance(query, answer)
    scores: dict = {
        "faithfulness": {"score": faith.score, "reasoning": faith.reasoning},
        "relevance": {"score": rel.score, "reasoning": rel.reasoning},
    }
    if reference:
        corr = await judge.correctness(query, answer, reference)
        scores["correctness"] = {"score": corr.score, "reasoning": corr.reasoning}

    return {**result, "judge_scores": scores}


def _compute_summary(results: list[dict]) -> dict:
    retrieval = {
        "hit_rate_candidates_at_20": round(hit_rate(results, "candidate_filenames", k=20), 4),
        "hit_rate_reranked_at_5": round(hit_rate(results, "reranked_filenames", k=5), 4),
        "mrr_reranked_at_5": round(mrr(results, "reranked_filenames", k=5), 4),
        "precision_at_5": round(precision_at_k(results, "reranked_filenames", k=5), 4),
    }
    generation = {
        "answer_presence_rate": round(answer_presence_rate(results), 4),
        "refusal_rate_on_oos": round(refusal_rate_on_oos(results), 4),
        "avg_citation_accuracy": round(avg_citation_accuracy(results), 4),
    }

    judged = [r for r in results if r.get("judge_scores")]
    faith_scores = [r["judge_scores"]["faithfulness"]["score"] for r in judged if "faithfulness" in r["judge_scores"]]
    rel_scores = [r["judge_scores"]["relevance"]["score"] for r in judged if "relevance" in r["judge_scores"]]
    corr_scores = [r["judge_scores"]["correctness"]["score"] for r in judged if "correctness" in r["judge_scores"]]

    judge_summary = {
        "faithfulness_avg": round(sum(faith_scores) / len(faith_scores), 4) if faith_scores else 0.0,
        "relevance_avg": round(sum(rel_scores) / len(rel_scores), 4) if rel_scores else 0.0,
        "correctness_avg": round(sum(corr_scores) / len(corr_scores), 4) if corr_scores else 0.0,
    }

    return {"retrieval": retrieval, "generation": generation, "judge": judge_summary}


def _check_thresholds(summary: dict) -> list[str]:
    failures = []
    hr = summary["retrieval"]["hit_rate_reranked_at_5"]
    faith = summary["judge"]["faithfulness_avg"]

    if hr < settings.eval_hit_rate_threshold:
        failures.append(
            f"hit_rate_reranked_at_5 {hr:.4f} < threshold {settings.eval_hit_rate_threshold}"
        )
    if faith < settings.eval_faithfulness_threshold:
        failures.append(
            f"faithfulness_avg {faith:.4f} < threshold {settings.eval_faithfulness_threshold}"
        )
    return failures


async def main() -> None:
    golden_set: list[dict] = json.loads(GOLDEN_SET_PATH.read_text())

    async with AsyncSessionLocal() as db:
        row = await db.execute(select(Workspace).where(Workspace.slug == "demo"))
        workspace = row.scalar_one_or_none()
        if workspace is None:
            print("ERROR: Demo workspace not found. Run `make seed` first.", file=sys.stderr)
            sys.exit(1)
        workspace_id = workspace.id

    embeddings = build_embedding_provider()
    llm = build_llm_provider()
    reranker = CrossEncoderReranker()
    print("Loading re-ranker model...")
    reranker._load()

    print(f"\nStage 1 — running {len(golden_set)} queries...")
    results: list[dict] = []
    async with AsyncSessionLocal() as db:
        retriever = HybridRetriever(chunk_repo=ChunkRepository(db), embeddings=embeddings)
        for row_data in golden_set:
            print(f"  [{row_data['id']}] {row_data['query'][:70]}")
            result = await _run_query(row_data, retriever, reranker, llm, workspace_id)
            results.append(result)

    print(f"\nStage 2 — LLM judge ({settings.eval_judge_model})...")
    judge = LLMJudge(model=settings.eval_judge_model, api_key=settings.openai_api_key)
    for i, result in enumerate(results):
        in_scope = bool(result["relevant_documents"])
        print(f"  [{result['id']}] {'judging' if in_scope else 'skipping (OOS)'}")
        results[i] = await _run_judge(result, judge)

    summary = _compute_summary(results)
    failures = _check_thresholds(summary)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_{ts}.json"
    out_path.write_text(
        json.dumps(
            {
                "run_at": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "threshold_failures": failures,
                "results": results,
            },
            indent=2,
            default=str,
        )
    )

    print("\n" + "=" * 60)
    print("EVAL SUMMARY")
    print("=" * 60)
    print("\nRetrieval:")
    for k, v in summary["retrieval"].items():
        print(f"  {k}: {v:.4f}")
    print("\nGeneration:")
    for k, v in summary["generation"].items():
        print(f"  {k}: {v:.4f}")
    print("\nLLM Judge:")
    for k, v in summary["judge"].items():
        print(f"  {k}: {v:.4f}")

    if failures:
        print("\nTHRESHOLD FAILURES:")
        for f in failures:
            print(f"  ✗ {f}")
        print(f"\nResults saved to {out_path}")
        sys.exit(1)
    else:
        print("\n✓ All thresholds passed")
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
