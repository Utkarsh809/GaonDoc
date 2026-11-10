import json
from pathlib import Path

import pytest

from eval.run_eval import score

SETS = sorted(Path(__file__).resolve().parent.parent.joinpath("eval").glob("*.json"))
SETS = [p for p in SETS if p.name in {"cases.json", "heldout.json", "heldout_2.json"}]


@pytest.mark.parametrize("path", SETS, ids=lambda p: p.name)
def test_eval_set_has_no_regressions(path):
    report = score(json.loads(path.read_text(encoding="utf-8")))
    assert report["emergency_recall"] == 1.0
    assert report["symptom_f1"] >= 0.95
