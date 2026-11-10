from app.pipeline.analyze import analyze
from app.pipeline.differential import suggest
from app.pipeline.state import CaseState, clinical_text


def view_of(text):
    state = CaseState()
    state.merge(analyze(text))
    return state, state.view()


def concepts(view):
    return {s["concept"] for s in view["symptoms"]}


def test_duration_and_negation():
    _, view = view_of("Mujhe teen din se tez bukhar hai aur sar dard, khansi nahi hai")
    assert concepts(view) == {"high_fever", "headache"}
    assert {d["concept"] for d in view["denied"]} == {"cough"}
    fever = next(s for s in view["symptoms"] if s["concept"] == "high_fever")
    assert fever["duration_days"] == 3


def test_persisting_fever_is_not_negated():
    _, view = view_of("bukhar nahi utar raha")
    assert "fever" in concepts(view)
    assert view["denied"] == []


def test_age_is_not_confused_with_duration():
    _, view = view_of("meri umar 45 saal ki hai, seene mein dard ho raha hai")
    assert view["age"] == 45
    chest = next(s for s in view["symptoms"] if s["concept"] == "chest_pain")
    assert chest["duration_days"] is None


def test_spelling_variants_and_devanagari():
    _, a = view_of("seene me dard")
    _, b = view_of("सीने में दर्द")
    _, c = view_of("Seena dard hai")
    assert concepts(a) == concepts(b) == concepts(c) == {"chest_pain"}


def test_hindi_number_words_and_units():
    _, view = view_of("do hafte se khansi hai")
    cough = view["symptoms"][0]
    assert cough["duration_days"] == 14
    assert cough["duration_text"] == "2 weeks"


def test_history_and_allergy():
    _, view = view_of("penicillin se allergy hai, sugar ki goli leta hoon")
    assert view["allergies"] == ["penicillin"]
    assert [h["concept"] for h in view["history"]] == ["diabetes_history"]


def test_english_negation():
    _, view = view_of("no fever, cough for 3 weeks")
    assert concepts(view) == {"cough"}
    assert [d["concept"] for d in view["denied"]] == ["fever"]


def test_clinical_text_renders():
    state, view = view_of("teen din se bukhar, khansi nahi")
    text = clinical_text(view)
    assert "Fever (3 days)" in text
    assert "Denies: Cough" in text


def test_differential_prioritises_tb_for_long_cough_with_weight_loss():
    state, _ = view_of("teen hafte se khansi aur wazan kam")
    assert suggest(state.present())[0]["id"] == "tb"


def test_pregnancy_is_context_not_symptom():
    _, view = view_of("main garbhvati hoon")
    assert view["pregnant"] is True
    assert view["symptoms"] == []


def test_intensifier_between_phrase_words():
    _, view = view_of("pet mein tez dard hai aur ulti bhi ho gayi")
    assert concepts(view) == {"abdominal_pain", "vomiting"}


def test_duration_does_not_leak_across_unrelated_symptom():
    _, view = view_of("teen hafte se khansi aur raat ko bukhar")
    by = {s["concept"]: s for s in view["symptoms"]}
    assert by["cough"]["duration_days"] == 21
    assert by["fever"]["duration_days"] is None


def test_duration_shared_across_conjunction_list():
    _, view = view_of("teen din se bukhar aur khansi")
    assert {s["concept"]: s["duration_days"] for s in view["symptoms"]} == {"fever": 3, "cough": 3}
