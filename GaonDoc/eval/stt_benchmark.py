import argparse
import asyncio
import json
import mimetypes
from pathlib import Path

from app.config import load_settings
from app.pipeline.analyze import analyze
from app.pipeline.state import CaseState
from app.providers.http_provider import HttpSTT

from .wer import wer


def concepts(text):
    state = CaseState()
    state.merge(analyze(text))
    return {s["concept"] for s in state.view()["symptoms"]}


async def run(manifest, language):
    stt = HttpSTT(load_settings())
    base = Path(manifest).parent
    items = json.loads(Path(manifest).read_text(encoding="utf-8"))
    rows, tp, fp, fn = [], 0, 0, 0
    for item in items:
        path = base / item["audio"]
        content_type = mimetypes.guess_type(path.name)[0] or "audio/wav"
        transcript = await stt.transcribe(path.read_bytes(), language, filename=path.name, content_type=content_type)
        got, want = concepts(transcript.text), concepts(item["reference"])
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
        rows.append({"audio": item["audio"], "reference": item["reference"], "hypothesis": transcript.text, "wer": round(wer(item["reference"], transcript.text), 3), "concept_missing": sorted(want - got), "concept_extra": sorted(got - want)})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    summary = {
        "items": len(rows),
        "mean_wer": round(sum(r["wer"] for r in rows) / len(rows), 3) if rows else None,
        "clinical_concept_precision": round(precision, 3),
        "clinical_concept_recall": round(recall, 3),
        "rows": rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Benchmark the configured STT provider on labelled audio.")
    parser.add_argument("manifest", help='JSON list of {"audio": "file.wav", "reference": "text"}, audio paths relative to the manifest')
    parser.add_argument("--lang", default="hi")
    args = parser.parse_args()
    asyncio.run(run(args.manifest, args.lang))


if __name__ == "__main__":
    main()
