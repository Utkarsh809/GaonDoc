import json
from pathlib import Path

from .analyze import concept_label

CONDITIONS = json.loads((Path(__file__).resolve().parent.parent / "data" / "conditions.json").read_text(encoding="utf-8"))["conditions"]
THRESHOLD = 0.4


def suggest(present, limit=3):
    results = []
    for condition in CONDITIONS:
        weights = condition["weights"]
        hits = [c for c in weights if c in present]
        if len(hits) < condition["min_hits"]:
            continue
        total = sum(weights[c] for c in hits)
        bonus = condition.get("duration")
        if bonus:
            days = present.get(bonus["concept"])
            if days is not None and days >= bonus["min_days"]:
                total += bonus["bonus"]
        normaliser = sum(sorted(weights.values(), reverse=True)[:3])
        score = min(1.0, total / normaliser)
        if score < THRESHOLD:
            continue
        results.append(
            {
                "id": condition["id"],
                "name": condition["name"],
                "score": round(score, 2),
                "supporting": [concept_label(c) for c in hits],
                "suggested_checks": condition["checks"],
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
