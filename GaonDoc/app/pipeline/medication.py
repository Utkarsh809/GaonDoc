import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .text import canon, ctokens, tokenize

_DB = json.loads((Path(__file__).resolve().parent.parent / "data" / "drugs.json").read_text(encoding="utf-8"))
DRUGS = {d["id"]: d for d in _DB["drugs"]}
FILLER = {
    "wali", "wala", "wale", "vali", "vala", "ki", "ka", "ke", "goli", "tablet", "tab", "tabs", "dawa", "dawai",
    "capsule", "cap", "syrup", "injection", "strip", "patta", "the", "a", "ek", "mg", "ml", "wali",
}
THRESHOLD = 0.75

_PARTNERS = {}
for _a, _b in _DB["lasa_pairs"]:
    _PARTNERS.setdefault(_a, []).append(_b)
    _PARTNERS.setdefault(_b, []).append(_a)

_COLLOQUIAL = [(tuple(ctokens(k)), ids) for k, ids in _DB["colloquial"].items()]

_DIGRAPHS = [("ph", "f"), ("kh", "k"), ("gh", "g"), ("sh", "s"), ("ch", "c"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("ck", "k")]
_LETTERS = {"x": "ks", "q": "k", "w": "v", "z": "j", "y": "i"}


def phonetic_key(text):
    s = re.sub(r"[^a-z]", "", canon(text))
    for a, b in _DIGRAPHS:
        s = s.replace(a, b)
    s = "".join(_LETTERS.get(c, c) for c in s)
    s = re.sub(r"(.)\1+", r"\1", s)
    if not s:
        return ""
    return s[0] + re.sub(r"[aeiou]", "", s[1:])


def _names(drug):
    return [drug["generic"], *drug.get("brands", []), *drug.get("aliases", [])]


_NAME_INDEX = []
for _drug in DRUGS.values():
    for _name in _names(_drug):
        _joined = " ".join(ctokens(_name))
        if _joined:
            _NAME_INDEX.append((_joined, phonetic_key(_name), _drug["id"], _name))


def _score(query, query_key, name, name_key):
    if query == name:
        return 1.0
    if len(query) < 4 or len(name) < 4:
        return 0.0
    plain = SequenceMatcher(None, query, name).ratio()
    phonetic = 0.97 * SequenceMatcher(None, query_key, name_key).ratio() if query_key and name_key else 0.0
    return max(plain, phonetic)


def _contains(tokens, key):
    n = len(key)
    return any(tuple(tokens[i : i + n]) == key for i in range(len(tokens) - n + 1))


def _candidate(drug_id, score, name):
    drug = DRUGS[drug_id]
    confidence = "exact" if score >= 0.99 else "likely" if score >= 0.88 else "possible"
    return {
        "id": drug_id,
        "generic": drug["generic"],
        "matched_name": name,
        "score": round(score, 2),
        "confidence": confidence,
        "use_en": drug["use_en"],
        "use_hi": drug["use_hi"],
        "lasa_partners": [DRUGS[p]["generic"] for p in _PARTNERS.get(drug_id, [])],
    }


PROMPT_EN = "Please read the name printed on the medicine strip and confirm."
PROMPT_HI = "कृपया दवा के पत्ते पर छपा नाम पढ़कर पुष्टि करें।"


def resolve(spoken, limit=3, threshold=THRESHOLD):
    tokens = ctokens(spoken)
    for key, ids in _COLLOQUIAL:
        if _contains(tokens, key):
            candidates = [_candidate(i, 0.5, " ".join(key)) for i in ids[:limit]]
            return {"query": spoken, "ambiguous": True, "needs_confirmation": True, "candidates": candidates, "prompt_en": PROMPT_EN, "prompt_hi": PROMPT_HI}
    core = [t for t in tokens if t not in FILLER and not t[0].isdigit()]
    if not core:
        return {"query": spoken, "ambiguous": False, "needs_confirmation": True, "candidates": [], "prompt_en": PROMPT_EN, "prompt_hi": PROMPT_HI}
    query = " ".join(core)
    query_key = phonetic_key(query)
    best = {}
    for name_c, name_key, drug_id, display in _NAME_INDEX:
        score = _score(query, query_key, name_c, name_key)
        if score >= threshold and score > best.get(drug_id, (0, ""))[0]:
            best[drug_id] = (score, display)
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    candidates = [_candidate(i, s, n) for i, (s, n) in ranked]
    needs = True
    if candidates:
        top = candidates[0]
        second = candidates[1]["score"] if len(candidates) > 1 else 0.0
        needs = top["score"] < 0.95 or (top["score"] - second) < 0.1 or (bool(top["lasa_partners"]) and top["score"] < 1.0)
    return {"query": spoken, "ambiguous": False, "needs_confirmation": needs, "candidates": candidates, "prompt_en": PROMPT_EN, "prompt_hi": PROMPT_HI}


def scan_mentions(text):
    raw, tokens = tokenize(text)
    mentions, covered = [], set()
    for key, ids in _COLLOQUIAL:
        n = len(key)
        for i in range(len(tokens) - n + 1):
            if tuple(tokens[i : i + n]) == key:
                covered.update(range(i, i + n))
                mentions.append(
                    {
                        "key": " ".join(key),
                        "spoken": " ".join(raw[i : i + n]),
                        "drug": None,
                        "generic": None,
                        "ambiguous": True,
                        "candidates": [DRUGS[d]["generic"] for d in ids],
                    }
                )
    for i, token in enumerate(tokens):
        if i in covered or token in FILLER or len(token) < 5 or token[0].isdigit():
            continue
        result = resolve(token, limit=1, threshold=0.9)
        if result["candidates"]:
            top = result["candidates"][0]
            mentions.append(
                {"key": top["id"], "spoken": raw[i], "drug": top["id"], "generic": top["generic"], "ambiguous": False, "candidates": [top["generic"]]}
            )
    return mentions


SLOT_NAMES = {1: ["morning"], 2: ["morning", "night"], 3: ["morning", "afternoon", "night"], 4: ["morning", "afternoon", "evening", "night"]}
FREQUENCY_PATTERN = {1: "1", 2: "1-1", 3: "1-1-1", 4: "1-1-1-1"}
SLOT_HI = {"morning": "सुबह", "afternoon": "दोपहर", "evening": "शाम", "night": "रात"}
SLOT_EN = {"morning": "in the morning", "afternoon": "in the afternoon", "evening": "in the evening", "night": "at night"}
TIMING_HI = {"before_food": "खाने से पहले", "after_food": "खाने के बाद", "with_food": "खाने के साथ", "empty_stomach": "खाली पेट"}
TIMING_EN = {"before_food": "before food", "after_food": "after food", "with_food": "with food", "empty_stomach": "on an empty stomach"}
CLOSING_EN = "This is based on the doctor's prescription. If you have any problem, ask your doctor or ASHA worker."
CLOSING_HI = "यह जानकारी डॉक्टर की पर्ची पर आधारित है। कोई भी परेशानी हो तो डॉक्टर या आशा दीदी से पूछें।"
_DOSE = re.compile(r"^(\d+(?:\.\d+)?)\s*(tablets?|tabs?|capsules?|caps?|ml)$", re.I)


def _slots(item):
    pattern = item.get("pattern") or FREQUENCY_PATTERN.get(item.get("frequency_per_day") or 0)
    if not pattern:
        return []
    digits = [int(d) for d in pattern.split("-")]
    names = SLOT_NAMES.get(len(digits), [])
    return [name for name, d in zip(names, digits) if d > 0]


def _dose_hi(dose):
    m = _DOSE.match(dose.strip())
    if not m:
        return dose
    unit = m.group(2).lower()
    word = "मिली" if unit == "ml" else "कैप्सूल" if unit.startswith("cap") else "गोली"
    return f"{m.group(1)} {word}"


def _join(parts, joiner):
    return joiner.join(parts)


def _warning(kind, en, hi):
    return {"type": kind, "text_en": en, "text_hi": hi}


def compose_guidance(items, case_view, reminder_times):
    resolved = []
    for item in items:
        result = resolve(item["drug"], limit=2)
        top = result["candidates"][0] if result["candidates"] and not result["ambiguous"] else None
        resolved.append((item, result, top))

    allergies = [canon(a) for a in case_view.get("allergies", [])]
    out_items, warnings, reminders = [], [], []
    ingredient_owner = {}

    for item, result, top in resolved:
        drug = DRUGS[top["id"]] if top else None
        generic = drug["generic"] if drug else None
        display = item["drug"].strip()
        if generic and generic.lower() not in display.lower():
            display = f"{display} ({generic})"
        item_warnings = []
        if not top or top["score"] < 0.88:
            item_warnings.append(_warning("unverified_name", f"'{item['drug']}' could not be matched confidently. Verify the name.", f"'{item['drug']}' का नाम पक्का नहीं मिला। नाम जांचें।"))
        if top and top["lasa_partners"] and top["score"] < 1.0:
            partners = ", ".join(top["lasa_partners"])
            item_warnings.append(_warning("lookalike", f"Sounds similar to {partners}. Confirm the intended medicine.", f"{partners} से मिलता-जुलता नाम है। सही दवा की पुष्टि करें।"))
        if drug:
            for ingredient in drug.get("contains", [drug["id"]]):
                if ingredient in ingredient_owner:
                    other = ingredient_owner[ingredient]
                    warnings.append(_warning("duplicate_ingredient", f"{ingredient.replace('_', ' ').title()} appears in both '{other}' and '{display}'. Risk of double dosing.", f"{ingredient.replace('_', ' ').title()} '{other}' और '{display}' दोनों में है। दोहरी खुराक का खतरा।"))
                ingredient_owner[ingredient] = display
            names = {canon(n) for n in _names(drug)} | set(drug.get("allergy_group", []))
            for allergen in allergies:
                if allergen in names or any(SequenceMatcher(None, allergen, n).ratio() >= 0.9 for n in names):
                    item_warnings.append(_warning("allergy", f"Patient reported allergy to '{allergen}'. Do not dispense without review.", f"मरीज़ ने '{allergen}' से एलर्जी बताई है। जांच के बिना न दें।"))
            if case_view.get("pregnant") and drug.get("pregnancy_check"):
                item_warnings.append(_warning("pregnancy_check", "Patient is pregnant. Confirm this medicine is appropriate in pregnancy.", "मरीज़ गर्भवती है। पुष्टि करें कि यह दवा गर्भावस्था में उचित है।"))
        slots = _slots(item)
        if not slots:
            item_warnings.append(_warning("schedule_missing", "No schedule given. Add a pattern like 1-0-1.", "समय नहीं दिया गया। 1-0-1 जैसा पैटर्न जोड़ें।"))

        dose = item.get("dose", "").strip()
        timing = item.get("timing")
        days = item.get("days")
        hi_parts = [display, ": "]
        en_parts = [display, ": "]
        pieces_hi = [p for p in [_dose_hi(dose) if dose else "", _join([SLOT_HI[s] for s in slots], " और ") if slots else "डॉक्टर के बताए समय पर", TIMING_HI.get(timing, ""), f"{days} दिन तक" if days else ""] if p]
        pieces_en = [p for p in [dose, _join([SLOT_EN[s] for s in slots], " and ") if slots else "as directed by the doctor", TIMING_EN.get(timing, ""), f"for {days} days" if days else ""] if p]
        text_hi = "".join(hi_parts) + ", ".join(pieces_hi) + "।"
        text_en = "".join(en_parts) + ", ".join(pieces_en) + "."
        tip_en = drug["tip_en"] if drug else ""
        tip_hi = drug["tip_hi"].rstrip(".।") + "।" if drug else ""
        for slot in slots:
            reminders.append(
                {
                    "time": reminder_times[slot],
                    "slot": slot,
                    "drug": display,
                    "text_en": f"Time to take {display}" + (f", {dose}" if dose else "") + (f", {TIMING_EN[timing]}" if timing else "") + ".",
                    "text_hi": f"{display} लेने का समय हो गया है" + (f", {_dose_hi(dose)}" if dose else "") + (f", {TIMING_HI[timing]}" if timing else "") + "।",
                }
            )
        out_items.append(
            {
                "input": item["drug"],
                "display": display,
                "matched": top["id"] if top else None,
                "generic": generic,
                "match_score": top["score"] if top else None,
                "use_en": drug["use_en"] if drug else None,
                "use_hi": drug["use_hi"] if drug else None,
                "slots": slots,
                "text_en": text_en,
                "text_hi": text_hi,
                "tip_en": tip_en,
                "tip_hi": tip_hi,
                "warnings": item_warnings,
            }
        )

    reminders.sort(key=lambda r: r["time"])
    spoken_en = " ".join(f"{i['text_en']} {i['tip_en']}".strip() for i in out_items) + " " + CLOSING_EN
    spoken_hi = " ".join(f"{i['text_hi']} {i['tip_hi']}".strip() for i in out_items) + " " + CLOSING_HI
    all_warnings = warnings + [w for i in out_items for w in i["warnings"]]
    return {"items": out_items, "warnings": all_warnings, "reminders": reminders, "spoken_en": spoken_en, "spoken_hi": spoken_hi}
