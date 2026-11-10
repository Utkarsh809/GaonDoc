import json
from pathlib import Path

from .text import UNIT_DAYS, UNIT_LABEL, duration_text, parse_number, sentences, tokenize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

STOP = {",", "aur", "and", "lekin", "but", "magar", "और", "लेकिन", "मगर"}
NEG_AFTER = {"nahi", "nahin", "nhi", "nai", "na", "नहीं", "नही"}
NEG_BEFORE = {"no", "koi", "without", "bina", "denies", "denied", "not", "कोई", "बिना"}
NEG_FOLLOW_OK = {"hai", "hain", "hua", "hui", "hue", "tha", "thi", "ho", "hota", "hoti", "h", "he", "aa", "aya", "ayi", "है", "हैं", "हुआ", "हुई", "हो"}
GAP_OK = {",", "aur", "and", "or", "ya", "hai", "hain", "ho", "raha", "rahi", "rahe", "है", "हैं", "और"}
AGE_FOLLOW = {"ka", "ki", "ke", "old", "का", "की", "के"}
AGE_MARKERS = {"umar", "umra", "age", "उम्र"}
ALLERGY_WORDS = {"allergy", "allergic", "alerji", "एलर्जी", "ऐलर्जी"}
ALLERGY_SKIP = {"no", "koi", "nahi", "hai", "ki", "ka", "ko", "se", "mujhe", "mereko", "hain", "any", "a", "an", "mera", "meri", "dawa", "dawai", ","}
RECENT_DAY_WORDS = {"kal": 1, "parso": 2, "कल": 1, "परसों": 2}


def _load():
    raw = json.loads((DATA_DIR / "medical_terms.json").read_text(encoding="utf-8"))
    index, meta = {}, {}
    for concept_id, spec in raw["concepts"].items():
        meta[concept_id] = {"label": spec["label"], "category": spec["category"]}
        for phrase in spec["phrases"]:
            index[tuple(tokenize(phrase)[1])] = concept_id
    return index, meta, max(len(key) for key in index)


INDEX, META, MAX_PHRASE = _load()
SKIPPABLE = {"tez", "bahut", "bohot", "bhot", "zyada", "jyada", "kafi", "halka", "halki", "thoda", "thodi", "bhi", "hi", "very", "severe", "sharp", "mild", "really", "too", "much", "lot", "तेज", "बहुत", "भी", "थोड़ा", "हल्का"}
MAX_SKIPS = 2

_BY_FIRST = {}
for _phrase, _concept in INDEX.items():
    _BY_FIRST.setdefault(_phrase[0], []).append((_phrase, _concept))
for _items in _BY_FIRST.values():
    _items.sort(key=lambda item: len(item[0]), reverse=True)


def concept_label(concept_id):
    return META[concept_id]["label"]


def _align(tokens, start, phrase):
    j = start
    for k, want in enumerate(phrase):
        if k > 0:
            skipped = 0
            while j < len(tokens) and tokens[j] != want and tokens[j] in SKIPPABLE and skipped < MAX_SKIPS:
                j += 1
                skipped += 1
        if j >= len(tokens) or tokens[j] != want:
            return None
        j += 1
    return j


def _scan(tokens):
    found, i, n = [], 0, len(tokens)
    while i < n:
        hit = None
        for phrase, concept in _BY_FIRST.get(tokens[i], ()):
            end = _align(tokens, i, phrase)
            if end is not None:
                hit = (end, concept)
                break
        if hit:
            found.append((i, hit[0], hit[1]))
            i = hit[0]
        else:
            i += 1
    return found


def _negated(tokens, start, end, boundaries):
    j = end
    limit = min(end + 3, len(tokens))
    while j < limit:
        token = tokens[j]
        if token in STOP or j in boundaries:
            break
        if token in NEG_AFTER:
            following = tokens[j + 1] if j + 1 < len(tokens) else None
            if following is None or following in NEG_FOLLOW_OK or following in STOP or (j + 1) in boundaries:
                return True
            break
        j += 1
    k = start - 1
    for _ in range(2):
        if k < 0:
            break
        token = tokens[k]
        if token in STOP:
            break
        if token in NEG_BEFORE:
            return True
        k -= 1
    return False


def _durations(tokens):
    found = []
    for i, token in enumerate(tokens):
        label = UNIT_LABEL.get(token)
        if label and i > 0:
            number = parse_number(tokens[i - 1])
            if number is None:
                continue
            if label == "year" and i + 1 < len(tokens) and tokens[i + 1] in AGE_FOLLOW:
                continue
            found.append((i, number * UNIT_DAYS[label], duration_text(number, label)))
        elif token in RECENT_DAY_WORDS and i + 1 < len(tokens) and tokens[i + 1] in {"se", "से"}:
            number = RECENT_DAY_WORDS[token]
            found.append((i, float(number), duration_text(number, "day")))
    return found


def _age(tokens):
    for i, token in enumerate(tokens):
        if UNIT_LABEL.get(token) == "year" and i > 0:
            number = parse_number(tokens[i - 1])
            following = tokens[i + 1] if i + 1 < len(tokens) else ""
            if number is not None and 0 <= number <= 120 and following in AGE_FOLLOW:
                return int(number)
        if token in AGE_MARKERS and i + 1 < len(tokens):
            number = parse_number(tokens[i + 1])
            if number is not None and 0 <= number <= 120:
                return int(number)
    return None


def _allergies(tokens):
    out = []
    for i, token in enumerate(tokens):
        if token not in ALLERGY_WORDS:
            continue
        if i >= 2 and tokens[i - 1] in {"se", "से"}:
            out.append(tokens[i - 2])
        elif i + 2 < len(tokens) and tokens[i + 1] == "to":
            out.append(tokens[i + 2])
        elif i >= 1 and tokens[i - 1] not in ALLERGY_SKIP:
            out.append(tokens[i - 1])
    return [a for a in out if a not in ALLERGY_SKIP]


def _attachable(tokens, found, index, start, end):
    if index < start:
        between = [f for f in found if f[1] <= start and f[0] > index]
        if not between:
            return True
        gap = tokens[max(f[1] for f in between) : start]
    else:
        between = [f for f in found if f[0] >= end and f[1] <= index]
        if not between:
            return True
        gap = tokens[end : min(f[0] for f in between)]
    return all(token in GAP_OK for token in gap)


def _distance(index, start, end):
    if index < start:
        return start - index
    if index >= end:
        return index - end + 1
    return 0


def analyze(text):
    matches, age, allergies = [], None, []
    for number, sentence in enumerate(sentences(text)):
        raw, tokens = tokenize(sentence)
        found = _scan(tokens)
        boundaries = {f[0] for f in found}
        durations = _durations(tokens)
        age = age or _age(tokens)
        for allergen in _allergies(tokens):
            if allergen not in allergies:
                allergies.append(allergen)
        for start, end, concept in found:
            negated = _negated(tokens, start, end, boundaries)
            duration = None
            reachable = [d for d in durations if _attachable(tokens, found, d[0], start, end)]
            if not negated and reachable:
                best = min(reachable, key=lambda d: _distance(d[0], start, end))
                if _distance(best[0], start, end) <= 6:
                    duration = best
            matches.append(
                {
                    "concept": concept,
                    "label": META[concept]["label"],
                    "category": META[concept]["category"],
                    "surface": " ".join(raw[start:end]),
                    "negated": negated,
                    "duration_days": duration[1] if duration else None,
                    "duration_text": duration[2] if duration else None,
                    "sentence": number,
                }
            )
    return {"matches": matches, "age": age, "allergies": allergies}


def glossary(analysis):
    seen, items = set(), []
    for m in analysis["matches"]:
        key = (m["surface"], m["label"])
        if key not in seen:
            seen.add(key)
            items.append(f"{m['surface']} = {m['label']}")
    return "; ".join(items)
