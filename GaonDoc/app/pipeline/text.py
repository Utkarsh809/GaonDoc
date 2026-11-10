import re
import unicodedata

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN = re.compile(r"[ऀ-ॣ०-ॿ]+|\d+(?:\.\d+)?|[a-z]+|,")
_SENTENCE = re.compile(r"(?<!\d)\.(?!\d)|[;!?।\n]+")
_LOCATIVE = {"me", "mai", "men"}
_ALIASES = {"sir": "sar", "khasi": "khansi"}


def canon(text):
    text = unicodedata.normalize("NFC", text).lower().translate(_DIGITS).replace("़", "")
    text = re.sub(r"aa+", "a", text)
    text = re.sub(r"(?:ee+|ii+)", "i", text)
    text = re.sub(r"(?:oo+|uu+)", "u", text)
    return text


def tokenize(text):
    prepared = unicodedata.normalize("NFC", text).lower().translate(_DIGITS)
    raw, tokens = [], []
    for piece in _TOKEN.findall(prepared):
        token = canon(piece)
        if token in _LOCATIVE:
            token = "mein"
        token = _ALIASES.get(token, token)
        if not token:
            continue
        raw.append(piece)
        tokens.append(token)
    return raw, tokens


def ctokens(text):
    return tokenize(text)[1]


def sentences(text):
    return [s for s in _SENTENCE.split(text) if s and s.strip()]


_NUMBER_SOURCE = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chah": 6,
    "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "pandrah": 15,
    "bees": 20, "tees": 30, "dedh": 1.5, "dhai": 2.5, "aadha": 0.5, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "half": 0.5,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "डेढ़": 1.5, "ढाई": 2.5, "आधा": 0.5,
}
NUMBER_WORDS = {canon(k): v for k, v in _NUMBER_SOURCE.items()}

_UNIT_SOURCE = {
    "day": ["din", "dino", "day", "days", "दिन"],
    "week": ["hafte", "hafta", "haftey", "week", "weeks", "saptah", "हफ्ते", "हफ्ता", "सप्ताह"],
    "month": ["mahine", "mahina", "mahino", "month", "months", "महीने", "महीना"],
    "year": ["sal", "saal", "year", "years", "varsh", "साल"],
    "hour": ["ghante", "ghanta", "hour", "hours", "hr", "hrs", "घंटे", "घंटा"],
}
UNIT_LABEL = {canon(w): label for label, words in _UNIT_SOURCE.items() for w in words}
UNIT_DAYS = {"day": 1.0, "week": 7.0, "month": 30.0, "year": 365.0, "hour": 1 / 24}


def parse_number(token):
    if token and token[0].isdigit():
        try:
            return float(token)
        except ValueError:
            return None
    return NUMBER_WORDS.get(token)


def duration_text(number, label):
    return f"{number:g} {label}{'' if number == 1 else 's'}"
