def _unique(filenames: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for f in filenames:
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


def hit_rate(results: list[dict], filenames_key: str, k: int) -> float:
    hits, total = 0, 0
    for r in results:
        if not r["relevant_documents"]:
            continue
        total += 1
        if any(f in r["relevant_documents"] for f in _unique(r[filenames_key])[:k]):
            hits += 1
    return hits / total if total else 0.0


def mrr(results: list[dict], filenames_key: str, k: int) -> float:
    rr_sum, total = 0.0, 0
    for r in results:
        if not r["relevant_documents"]:
            continue
        total += 1
        for rank, filename in enumerate(_unique(r[filenames_key])[:k], start=1):
            if filename in r["relevant_documents"]:
                rr_sum += 1.0 / rank
                break
    return rr_sum / total if total else 0.0


def precision_at_k(results: list[dict], filenames_key: str, k: int) -> float:
    precisions = []
    for r in results:
        if not r["relevant_documents"]:
            continue
        filenames = _unique(r[filenames_key])[:k]
        relevant = sum(1 for f in filenames if f in r["relevant_documents"])
        precisions.append(relevant / k)
    return sum(precisions) / len(precisions) if precisions else 0.0
