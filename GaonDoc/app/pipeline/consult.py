import base64

import httpx

from ..providers.base import ProviderError
from .analyze import analyze, glossary
from .differential import suggest
from .llm_extract import extract_concepts, supplement
from .medication import compose_guidance, scan_mentions
from .redflags import evaluate
from .state import clinical_text
from .translate import localized, output_language, translate

TTS_ERRORS = (ProviderError, httpx.HTTPError, ValueError)
SAFETY_NET_EN = "Go to the hospital immediately if you have: difficulty breathing, chest pain, fainting, fits, fever that does not come down, continuous vomiting, or bleeding."
SAFETY_NET_HI = "इनमें से कुछ भी हो तो तुरंत अस्पताल जाएं: सांस लेने में तकलीफ, सीने में दर्द, बेहोशी, दौरे, न उतरने वाला बुखार, लगातार उल्टी या खून बहना।"
DISCLAIMER = "Decision support only. Not a diagnosis. A qualified clinician must review."


async def speak(providers, text, language):
    try:
        speech = await providers.tts.synthesize(text, language)
    except TTS_ERRORS:
        return None
    return {"base64": base64.b64encode(speech.audio).decode("ascii"), "mime": speech.mime}


async def process_turn(session, providers, speaker, text, confidence=None, speak_translation=False):
    patient = speaker == "patient"
    src = session.patient_language if patient else session.doctor_language
    dst = session.doctor_language if patient else session.patient_language
    analysis = analyze(text)
    translation, mode = await translate(providers.llm, text, src, dst, glossary(analysis) if src == "hi" else "")
    number = session.add_turn(speaker, text, translation)
    result = {
        "turn": number,
        "speaker": speaker,
        "transcript": text,
        "stt_confidence": confidence,
        "needs_repeat": confidence is not None and confidence < 0.6,
        "translation": translation,
        "translation_mode": mode,
        "translation_warning": "Translation provider not configured or failed; text shown untranslated." if mode == "passthrough" else None,
        "audio": None,
    }
    if patient:
        english, english_mode = (translation, mode) if dst == "en" else await translate(providers.llm, text, src, "en")
        mentions = scan_mentions(text)
        session.state.merge(analysis, mentions)
        if src not in ("hi", "en") and english_mode == "llm":
            session.state.merge(analyze(english), scan_mentions(english))
        extraction_source = "rules"
        if providers.llm is not None:
            found = await extract_concepts(providers.llm, text)
            if found is None:
                extraction_source = "rules (model unavailable)"
            else:
                extraction_source = "rules + model"
                session.state.merge(supplement(found, analysis), [])
        view = session.state.view()
        present = session.state.present()
        flags = evaluate(present)
        new = [f for f in flags if f["id"] not in session.seen_flags]
        session.seen_flags.update(f["id"] for f in new)
        alert = None
        emergency = next((f for f in new if f["level"] == "emergency"), None)
        if emergency:
            alert_text, used = await localized(providers.llm, emergency["message_en"], emergency["message_hi"], session.patient_language)
            alert = {"id": emergency["id"], "level": "emergency", "text": alert_text, "language": used, "audio": await speak(providers, alert_text, used)}
        result.update(
            {
                "extraction": view,
                "extraction_source": extraction_source,
                "clinical_summary": clinical_text(view),
                "red_flags": flags,
                "new_red_flags": new,
                "alert": alert,
                "possible_conditions": suggest(present),
                "disclaimer": DISCLAIMER,
            }
        )
        if speak_translation and mode != "passthrough":
            result["audio"] = await speak(providers, translation, output_language(dst, providers.llm))
    elif mode != "passthrough":
        result["audio"] = await speak(providers, translation, output_language(dst, providers.llm))
    return result


async def process_prescription(session, providers, items, reminder_times):
    guidance = compose_guidance(items, session.state.view(), reminder_times)
    spoken, used = await localized(providers.llm, guidance["spoken_en"], guidance["spoken_hi"], session.patient_language)
    guidance["spoken"] = {"text": spoken, "language": used, "audio": await speak(providers, spoken, used)}
    session.prescription = guidance
    return guidance


def build_summary(session):
    view = session.state.view()
    present = session.state.present()
    flags = evaluate(present)
    conditions = suggest(present)
    rx = session.prescription

    doctor = ["VISIT SUMMARY", clinical_text(view) or "No clinical details captured."]
    if flags:
        doctor.append("Alerts: " + "; ".join(f"[{f['level']}] {f['message_en']}" for f in flags))
    if conditions:
        doctor.append("Possible conditions (decision support): " + "; ".join(f"{c['name']} ({int(c['score'] * 100)}%)" for c in conditions))
    if rx:
        doctor.append("Prescription: " + " ".join(i["text_en"] for i in rx["items"]))
        if rx["warnings"]:
            doctor.append("Prescription warnings: " + "; ".join(w["text_en"] for w in rx["warnings"]))
    doctor.append(DISCLAIMER)

    said = [s["phrases"][0] for s in view["symptoms"] if s["phrases"]]
    patient_hi = ["आज की जांच का सार"]
    patient_en = ["Summary of today's visit"]
    if said:
        patient_hi.append("आपने बताया: " + ", ".join(said) + "।")
        patient_en.append("You told us: " + ", ".join(said) + ".")
    for flag in flags[:3]:
        patient_hi.append(flag["message_hi"])
        patient_en.append(flag["message_en"])
    if rx:
        patient_hi.append("दवाइयाँ: " + " ".join(f"{i['text_hi']} {i['tip_hi']}".strip() for i in rx["items"]))
        patient_en.append("Medicines: " + " ".join(f"{i['text_en']} {i['tip_en']}".strip() for i in rx["items"]))
    patient_hi.append(SAFETY_NET_HI)
    patient_en.append(SAFETY_NET_EN)

    return {
        "case": view,
        "doctor_summary": "\n".join(doctor),
        "patient_summary": {"hi": "\n".join(patient_hi), "en": "\n".join(patient_en)},
        "red_flags": flags,
        "possible_conditions": conditions,
        "prescription": rx,
        "transcript": session.turns,
        "disclaimer": DISCLAIMER,
    }
