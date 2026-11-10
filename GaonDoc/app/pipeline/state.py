SYMPTOM_CATEGORIES = {"symptom", "injury", "mental"}


class CaseState:
    def __init__(self):
        self.concepts = {}
        self.age = None
        self.allergies = []
        self.medications = []

    def merge(self, analysis, medications=()):
        for m in analysis["matches"]:
            entry = self.concepts.setdefault(
                m["concept"],
                {
                    "concept": m["concept"],
                    "label": m["label"],
                    "category": m["category"],
                    "phrases": [],
                    "duration_days": None,
                    "duration_text": None,
                    "negated": True,
                },
            )
            if not m["negated"]:
                entry["negated"] = False
                days = m["duration_days"]
                if days is not None and (entry["duration_days"] is None or days > entry["duration_days"]):
                    entry["duration_days"] = days
                    entry["duration_text"] = m["duration_text"]
            if m["surface"] not in entry["phrases"]:
                entry["phrases"].append(m["surface"])
        self.age = analysis["age"] or self.age
        for allergen in analysis["allergies"]:
            if allergen not in self.allergies:
                self.allergies.append(allergen)
        known = {med["key"] for med in self.medications}
        for med in medications:
            if med["key"] not in known:
                known.add(med["key"])
                self.medications.append(med)

    def present(self):
        return {cid: e["duration_days"] for cid, e in self.concepts.items() if not e["negated"]}

    def view(self):
        present = [e for e in self.concepts.values() if not e["negated"]]

        def pick(categories):
            return [
                {
                    "concept": e["concept"],
                    "label": e["label"],
                    "phrases": e["phrases"],
                    "duration_days": e["duration_days"],
                    "duration_text": e["duration_text"],
                }
                for e in present
                if e["category"] in categories
            ]

        return {
            "age": self.age,
            "pregnant": any(e["concept"] == "pregnancy" for e in present),
            "symptoms": pick(SYMPTOM_CATEGORIES),
            "history": pick({"history"}),
            "denied": [{"concept": e["concept"], "label": e["label"]} for e in self.concepts.values() if e["negated"]],
            "allergies": list(self.allergies),
            "medications": list(self.medications),
        }


def clinical_text(view):
    parts = []
    if view["age"] is not None:
        parts.append(f"Age {view['age']} (reported).")
    if view["pregnant"]:
        parts.append("Pregnant (reported).")
    if view["symptoms"]:
        items = [s["label"] + (f" ({s['duration_text']})" if s["duration_text"] else "") for s in view["symptoms"]]
        parts.append("Presenting: " + ", ".join(items) + ".")
    if view["denied"]:
        parts.append("Denies: " + ", ".join(d["label"] for d in view["denied"]) + ".")
    if view["history"]:
        parts.append("History: " + ", ".join(h["label"] for h in view["history"]) + ".")
    if view["allergies"]:
        parts.append("Allergies reported: " + ", ".join(view["allergies"]) + ".")
    if view["medications"]:
        names = [m["generic"] or m["spoken"] for m in view["medications"]]
        parts.append("Medicines mentioned: " + ", ".join(names) + ".")
    return " ".join(parts)
