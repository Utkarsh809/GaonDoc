from ..providers.base import ProviderError

LANG_NAMES = {
    "hi": "Hindi", "en": "English", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi",
    "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu", "or": "Odia",
    "as": "Assamese", "bho": "Bhojpuri", "mai": "Maithili", "raj": "Rajasthani",
}


def lang_name(code):
    return LANG_NAMES.get(code, code)


def output_language(code, llm):
    return code if code in ("hi", "en") or llm is not None else "hi"


async def translate(llm, text, src, dst, glossary=""):
    if not text.strip() or src == dst:
        return text, "same"
    if llm is None:
        return text, "passthrough"
    system = (
        f"You are a medical interpreter between a village patient and a doctor. "
        f"Translate faithfully from {lang_name(src)} to {lang_name(dst)}. "
        f"Preserve every symptom, duration, body part, medicine name, dose, number and negation. "
        f"Do not add, diagnose, advise or explain. Output only the translation."
    )
    if glossary:
        system += f" Colloquial terms seen in the source and their clinical meaning: {glossary}."
    try:
        out = await llm.complete(system, text)
    except ProviderError:
        return text, "passthrough"
    return (out, "llm") if out else (text, "passthrough")


async def localized(llm, en, hi, lang):
    if lang == "hi":
        return hi, "hi"
    if lang == "en":
        return en, "en"
    if llm is not None:
        text, mode = await translate(llm, en, "en", lang)
        if mode == "llm":
            return text, lang
    return hi, "hi"
