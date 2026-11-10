import json
from pathlib import Path

RULES = json.loads((Path(__file__).resolve().parent.parent / "data" / "redflags.json").read_text(encoding="utf-8"))["rules"]
ORDER = {"emergency": 0, "urgent": 1, "advisory": 2}


def evaluate(present):
    out = []
    for rule in RULES:
        any_of = rule.get("any", [])
        all_of = rule.get("all", [])
        if not any_of and not all_of:
            continue
        if any(c not in present for c in all_of):
            continue
        hits = [c for c in any_of if c in present]
        if any_of and not hits:
            continue
        threshold = rule.get("min_days")
        if threshold is not None:
            durations = [present[c] for c in (hits or all_of) if present[c] is not None]
            if not durations or max(durations) < threshold:
                continue
        out.append(
            {
                "id": rule["id"],
                "level": rule["level"],
                "message_en": rule["en"],
                "message_hi": rule["hi"],
                "matched": hits + all_of,
            }
        )
    out.sort(key=lambda f: ORDER[f["level"]])
    return out
