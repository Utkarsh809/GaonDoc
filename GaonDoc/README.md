# GaonDoc

Voice health bridge for rural patients and clinicians. A patient speaks in their own language or Hinglish; the clinician sees a clinical rendering, structured case sheet, red-flag alerts and decision-support suggestions; the patient hears medication instructions and emergency alerts back in their language.

Decision support only. It does not diagnose. A clinician reviews every output.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000. Default `PROVIDER_MODE=mock` needs no keys: typed input works, TTS returns silent WAV placeholders, translation is passthrough. Use it to explore the flow.

## Connect your keys

Set `PROVIDER_MODE=http` and fill `.env`. The adapters are config-driven, so most REST APIs work without code changes.

| Provider | Required | Shape |
|---|---|---|
| STT | `STT_URL`, `STT_KEY` | multipart upload (`STT_FILE_FIELD`, `STT_LANG_FIELD`), JSON response read at `STT_TEXT_PATH` (dotted, e.g. `results.0.text`), optional `STT_CONF_PATH` |
| TTS | `TTS_URL`, `TTS_KEY` | JSON body (`TTS_TEXT_FIELD`, `TTS_LANG_FIELD`), binary audio or base64 at `TTS_AUDIO_PATH` when `TTS_RESPONSE=json_base64` |
| LLM (optional) | `LLM_URL`, `LLM_KEY`, `LLM_MODEL` | OpenAI-style chat completions, text at `LLM_TEXT_PATH` |

Language codes differ per vendor: map them with `STT_LANG_MAP='{"hi":"hi-IN"}'` and `TTS_LANG_MAP`. Extra fixed fields go in `STT_EXTRA` / `TTS_EXTRA` as JSON.

Without an LLM, translation is unavailable (the API says so instead of faking it), and only Hindi/Hinglish/English extraction works. With one, you get translation to and from every language your STT/TTS support, plus a model pass that backs up the rule-based extractor for missed findings.

## How it works

1. STT transcribes the speaker's audio.
2. `analyze` normalizes spelling variants, matches colloquial phrases (Roman and Devanagari) to clinical concepts, handles negation ("bukhar nahi hai"), durations ("do hafte se") and age.
3. LLM (if configured) translates with a glossary of the matched terms and supplements missed concepts. It cannot override an explicit denial.
4. Red-flag rules run on the whole session state, so findings combine across turns (pregnancy + bleeding).
5. Emergencies trigger a spoken alert in the patient's language, once per flag.
6. Differential suggestions rank conditions with suggested checks for the clinician.
7. The prescriber enters a prescription; the system resolves drug names phonetically, flags look-alike pairs, duplicate ingredients, reported allergies and pregnancy checks, then speaks Hindi/English instructions and builds reminders.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/sessions` | Start (requires `consent: true`) |
| POST | `/api/sessions/{id}/turn` | Form: `speaker`, `audio` or `text` |
| POST | `/api/sessions/{id}/prescription` | Requires `prescriber_confirmed: true` |
| GET | `/api/sessions/{id}/summary` | Doctor and patient summaries |
| POST | `/api/medication/resolve` | Resolve a spoken drug name |
| DELETE | `/api/sessions/{id}` | Discard session |

Sessions live in memory with a TTL. Audio is never stored.

## Test and evaluate

```bash
pytest
python -m eval.run_eval                  # extraction and red-flag metrics
python -m eval.stt_benchmark manifest.json --lang hi   # your STT on labelled audio
```

`manifest.json` is a list of `{"audio": "clip.wav", "reference": "teen din se bukhar hai"}`. The benchmark reports WER and clinical-concept precision/recall, which matters more than WER: a transcript can be wrong by 20% of words and still carry every symptom.

## Limits to know

- The bundled eval sets were written together with the lexicon, so they are regression tests, not accuracy estimates. A first unseen probe scored about 70% symptom recall before lexicon fixes. Measure on speech from your target villages and extend `app/data/medical_terms.json`.
- The lexicon covers Hindi/Hinglish and English. Other languages depend on the LLM path.
- Drug data (`drugs.json`) and condition rules (`conditions.json`) are a starter set. Have a clinician review them before any pilot.
- Red-flag messages and drug tips are general first-aid and counselling statements, not individualized advice.

## Layout

```
app/
  main.py            API
  providers/         STT/TTS/LLM adapters, mock mode
  pipeline/          analyze, redflags, differential, medication, translate, consult
  data/              medical_terms, redflags, conditions, drugs
  static/            voice PWA
eval/                eval harness and benchmark
tests/
```
