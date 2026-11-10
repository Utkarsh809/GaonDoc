from app.pipeline.analyze import analyze
from app.pipeline.redflags import evaluate
from app.pipeline.state import CaseState


def flags(*texts):
    state = CaseState()
    for text in texts:
        state.merge(analyze(text))
    return {f["id"]: f["level"] for f in evaluate(state.present())}


def test_chest_pain_is_emergency():
    assert flags("seene mein dard hai")["chest_pain"] == "emergency"


def test_negated_emergency_does_not_fire():
    assert "chest_pain" not in flags("seene mein dard nahi hai")


def test_pregnancy_bleeding_combines_across_turns():
    assert "pregnancy_bleeding" not in flags("main garbhvati hoon")
    assert flags("main garbhvati hoon", "ab khoon aa raha hai")["pregnancy_bleeding"] == "emergency"


def test_fever_with_stiff_neck():
    assert flags("bukhar hai aur gardan akad gayi")["meningitis_signs"] == "emergency"


def test_cough_duration_threshold():
    assert "cough_2_weeks" not in flags("paanch din se khansi")
    assert flags("teen hafte se khansi")["cough_2_weeks"] == "advisory"


def test_diarrhea_with_vomiting_is_urgent():
    assert flags("patle dast aur ulti")["diarrhea_vomiting"] == "urgent"


def test_suicidal_statement_is_emergency_with_helpline():
    result = evaluate({"self_harm_ideation": None})
    assert result[0]["level"] == "emergency"
    assert "14416" in result[0]["message_en"]


def test_emergencies_sorted_first():
    result = evaluate({"fever": 5.0, "chest_pain": None})
    assert result[0]["level"] == "emergency"
    assert result[-1]["level"] == "advisory"
