from app.config import Settings
from app.pipeline.medication import compose_guidance, phonetic_key, resolve, scan_mentions

TIMES = Settings().reminder_times


def test_phonetic_key_matches_mispronunciation():
    assert phonetic_key("metfarmin") == phonetic_key("metformin")


def test_mispronounced_name_resolves_and_needs_confirmation():
    result = resolve("metfarmin")
    top = result["candidates"][0]
    assert top["generic"] == "Metformin"
    assert "Metronidazole" in top["lasa_partners"]
    assert result["needs_confirmation"] is True


def test_brand_with_filler_words_resolves_exactly():
    result = resolve("dolo wali goli")
    assert result["candidates"][0]["generic"] == "Paracetamol"
    assert result["needs_confirmation"] is False


def test_strength_digits_are_ignored():
    assert resolve("Dolo 650")["candidates"][0]["generic"] == "Paracetamol"


def test_class_level_description_is_ambiguous():
    result = resolve("sugar ki goli")
    assert result["ambiguous"] is True
    assert result["needs_confirmation"] is True
    assert {c["generic"] for c in result["candidates"]} >= {"Metformin", "Glimepiride"}


def test_unknown_name_returns_no_candidates():
    assert resolve("xyzabc")["candidates"] == []


def test_scan_mentions_finds_free_text_drugs():
    found = scan_mentions("main metformin leta hoon aur sugar ki goli bhi")
    keys = {m["key"] for m in found}
    assert "metformin" in keys
    assert "sugar ki goli" in keys


def test_guidance_schedule_and_reminders():
    result = compose_guidance([{"drug": "Metformin", "dose": "1 tablet", "pattern": "1-0-1", "days": 5, "timing": "after_food"}], {"allergies": [], "pregnant": False}, TIMES)
    item = result["items"][0]
    assert item["slots"] == ["morning", "night"]
    assert "सुबह और रात" in item["text_hi"]
    assert "खाने के बाद" in item["text_hi"]
    assert [r["time"] for r in result["reminders"]] == ["08:00", "21:00"]


def test_duplicate_ingredient_warning():
    result = compose_guidance(
        [{"drug": "Dolo 650", "dose": "1 tablet", "pattern": "1-0-1", "days": 3}, {"drug": "Combiflam", "dose": "1 tablet", "pattern": "1-0-1", "days": 3}],
        {"allergies": [], "pregnant": False},
        TIMES,
    )
    assert "duplicate_ingredient" in {w["type"] for w in result["warnings"]}


def test_allergy_and_pregnancy_warnings():
    result = compose_guidance(
        [{"drug": "Augmentin", "dose": "1 tablet", "pattern": "1-0-1", "days": 5}, {"drug": "Ibuprofen", "dose": "1 tablet", "pattern": "1-0-1", "days": 2}],
        {"allergies": ["penicillin"], "pregnant": True},
        TIMES,
    )
    kinds = [w["type"] for w in result["warnings"]]
    assert "allergy" in kinds
    assert "pregnancy_check" in kinds


def test_missing_schedule_is_flagged_and_unknown_drug_unverified():
    result = compose_guidance([{"drug": "Zorblax", "dose": ""}], {"allergies": [], "pregnant": False}, TIMES)
    kinds = {w["type"] for w in result["warnings"]}
    assert {"schedule_missing", "unverified_name"} <= kinds
    assert result["reminders"] == []
