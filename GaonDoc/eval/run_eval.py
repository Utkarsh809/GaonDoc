import json
import sys
from pathlib import Path

from app.pipeline.analyze import analyze
from app.pipeline.redflags import RULES, evaluate
from app.pipeline.state import CaseState

LEVEL = {rule["id"]: rule["level"] for rule in RULES}


def score(cases):
    tp = fp = fn = 0
    denied_total = denied_hit = 0
    flags_total = flags_hit = exact = 0
    critical_total = critical_hit = 0
    failures = []
    for case in cases:
        state = CaseState()
        state.merge(analyze(case["text"]))
        view = state.view()
        got = {s["concept"] for s in view["symptoms"]}
        want = set(case["symptoms"])
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
        got_denied = {d["concept"] for d in view["denied"]}
        denied_total += len(case["denied"])
        denied_hit += len(got_denied & set(case["denied"]))
        got_flags = {f["id"] for f in evaluate(state.present())}
        want_flags = set(case["flags"])
        flags_total += len(want_flags)
        flags_hit += len(got_flags & want_flags)
        critical = {f for f in want_flags if LEVEL[f] == "emergency"}
        critical_total += len(critical)
        critical_hit += len(got_flags & critical)
        exact += got_flags == want_flags
        if got != want or not set(case["denied"]) <= got_denied or got_flags != want_flags:
            failures.append({"text": case["text"], "missing": sorted(want - got), "extra": sorted(got - want), "flags_missing": sorted(want_flags - got_flags), "flags_extra": sorted(got_flags - want_flags), "denied_missing": sorted(set(case["denied"]) - got_denied)})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "cases": len(cases),
        "symptom_precision": round(precision, 3),
        "symptom_recall": round(recall, 3),
        "symptom_f1": round(f1, 3),
        "negation_recall": round(denied_hit / denied_total, 3) if denied_total else None,
        "red_flag_recall": round(flags_hit / flags_total, 3) if flags_total else None,
        "red_flag_exact_match": round(exact / len(cases), 3),
        "emergency_recall": round(critical_hit / critical_total, 3) if critical_total else None,
        "failures": failures,
    }


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("cases.json")
    report = score(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["emergency_recall"] in (None, 1.0) else 1)


if __name__ == "__main__":
    main()
