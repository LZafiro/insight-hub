import re


def is_refusal(answer: str) -> bool:
    return "don't have enough information" in answer.lower()


def citation_accuracy(answer: str, num_chunks: int) -> float:
    citations = [int(c) for c in re.findall(r"\[(\d+)\]", answer)]
    if not citations:
        return 1.0
    valid = sum(1 for c in citations if 1 <= c <= num_chunks)
    return valid / len(citations)


def answer_presence_rate(results: list[dict]) -> float:
    with_context = [r for r in results if r["relevant_documents"]]
    if not with_context:
        return 0.0
    answered = sum(1 for r in with_context if not is_refusal(r["answer"]))
    return answered / len(with_context)


def refusal_rate_on_oos(results: list[dict]) -> float:
    oos = [r for r in results if not r["relevant_documents"]]
    if not oos:
        return 1.0
    refused = sum(1 for r in oos if is_refusal(r["answer"]))
    return refused / len(oos)


def avg_citation_accuracy(results: list[dict]) -> float:
    scores = [
        citation_accuracy(r["answer"], r["num_reranked_chunks"])
        for r in results
        if r["relevant_documents"] and not is_refusal(r["answer"])
    ]
    return sum(scores) / len(scores) if scores else 1.0
