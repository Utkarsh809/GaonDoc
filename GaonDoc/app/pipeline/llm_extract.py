import json
import re

from ..providers.base import ProviderError
from .analyze import META

CONCEPTS = "; ".join(f"{cid} = {meta['label']}" for cid, meta in META.items())
SYSTEM = (
    "You extract clinical findings from what a village patient said, in any Indian language or Hinglish. "
    'Return ONLY JSON: {"present": [ids the patient reports having now], "denied": [ids the patient explicitly says they do not have]}. '
    f"Use only these ids: {CONCEPTS}. "
    "Include an id only if it is clearly stated. Never guess, infer or diagnose."
)


async def extract_concepts(llm, text):
    try:
        raw = await llm.complete(SYSTEM, text)
    except ProviderError:
        return None
    found = re.search(r"\{.*\}", raw, re.S)
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
    except ValueError:
        return None

    def clean(key):
        values = data.get(key, [])
        return [c for c in values if isinstance(c, str) and c in META] if isinstance(values, list) else []

    return {"present": clean("present"), "denied": clean("denied")}


def supplement(found, analysis):
    ruled_out = {m["concept"] for m in analysis["matches"] if m["negated"]}
    have = {m["concept"] for m in analysis["matches"] if not m["negated"]}
    matches = []
    for concept in found["present"]:
        if concept in have or concept in ruled_out:
            continue
        meta = META[concept]
        matches.append(
            {
                "concept": concept,
                "label": meta["label"],
                "category": meta["category"],
                "surface": "(model-detected)",
                "negated": False,
                "duration_days": None,
                "duration_text": None,
                "sentence": -1,
            }
        )
    return {"matches": matches, "age": None, "allergies": []}
