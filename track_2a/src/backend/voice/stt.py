"""Speech to text with Whisper (faster-whisper / CTranslate2) for spoken answers: POST /api/v1/transcribe.

- de and gsw: a Swiss German fine-tune of whisper-large-v3-turbo. Mundart in, Standard German text out,
  which is what the analysis expects anyway.
- fr and it: the normal whisper-large-v3-turbo.

Both run on the CPU (int8) and stay in memory after the first use. Settings (env):
    STT_ENABLED=false        switch off (the frontend then uses the browser's speech recognition)
    STT_MODEL_DE=<repo>      model for de/gsw (a Hugging Face repo with a CTranslate2 model)
    STT_MODEL=<name>         model for fr/it (a faster-whisper size such as "small", or a repo)
    STT_THREADS=4            CPU threads per model (0 = all)
"""

import io
import logging
import os
import re
import threading
import time

from backend.voice import MODELS_DIR, VoiceUnavailable, flag

logger = logging.getLogger("voice.stt")

SWISS_GERMAN = "nebi/whisper-large-v3-turbo-swiss-german-ct2-int8"  # CTranslate2 build of Flurin17's fine-tune
MULTILINGUAL = "large-v3-turbo"
# The Swiss German build comes without tokenizer.json; this is the tokenizer of the model it was trained from.
TOKENIZER_FROM = "openai/whisper-large-v3-turbo"

SAMPLE_RATE = 16000
MAX_SECONDS = 60
LANGUAGES = ("de", "fr", "it", "gsw")

_models: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return flag("STT_ENABLED", True)


def model_name(language: str) -> str:
    if language in ("de", "gsw"):
        return os.environ.get("STT_MODEL_DE") or SWISS_GERMAN
    return os.environ.get("STT_MODEL") or MULTILINGUAL


def _model_path(name: str) -> str:
    """A local folder for a Hugging Face repo (downloaded once), or the size name for faster-whisper."""
    if "/" not in name:
        return name  # e.g. "large-v3-turbo": faster-whisper downloads it into MODELS_DIR itself
    from huggingface_hub import hf_hub_download, snapshot_download

    folder = MODELS_DIR / "whisper" / name.replace("/", "--")
    snapshot_download(name, local_dir=folder)
    if not (folder / "tokenizer.json").exists():
        hf_hub_download(TOKENIZER_FROM, "tokenizer.json", local_dir=folder)
    return str(folder)


def load(name: str):
    """The model, loaded (and downloaded) on first use. Thread-safe."""
    with _lock:
        if name not in _models:
            from faster_whisper import WhisperModel

            started = time.monotonic()
            try:
                _models[name] = WhisperModel(
                    _model_path(name), device="cpu", compute_type="int8",
                    cpu_threads=int(os.environ.get("STT_THREADS") or 0),
                    download_root=str(MODELS_DIR / "whisper"),
                )
            except Exception as exc:
                logger.exception("Whisper model could not be loaded")
                raise VoiceUnavailable(f"speech-to-text model {name} could not be loaded: {exc}") from exc
            logger.info("whisper model %s loaded in %.1f s", name, time.monotonic() - started)
        return _models[name]


def preload() -> None:
    """Load the models at startup, so that the first spoken answer is not slow."""
    for name in dict.fromkeys(model_name(lang) for lang in LANGUAGES):
        try:
            load(name)
        except VoiceUnavailable:
            pass  # already logged; the endpoint answers 503 until a later load works


def decode(data: bytes):
    """Any browser recording (webm, ogg, mp4, wav) -> 16 kHz mono samples. ValueError if it is not audio."""
    from faster_whisper.audio import decode_audio

    try:
        return decode_audio(io.BytesIO(data), sampling_rate=SAMPLE_RATE)
    except Exception as exc:
        raise ValueError(f"audio could not be read: {type(exc).__name__}") from exc


# Whisper's initial_prompt: a sentence with the words of the interview helps it spell occupation and company names
# and typical terms ("Schnupperlehre") instead of guessing similar-sounding words.
_HINT = {
    "de": "Bewerbungsgespräch für eine Lehrstelle als {occupation}{company}. Schnupperlehre, Lehrbetrieb, Berufsschule, Lernende.",
    "fr": "Entretien d'embauche pour un apprentissage de {occupation}{company}. Stage, entreprise formatrice, école professionnelle.",
    "it": "Colloquio per un apprendistato come {occupation}{company}. Stage, azienda formatrice, scuola professionale.",
}
_AT = {"de": " bei {}", "fr": " chez {}", "it": " presso {}"}


def vocabulary_hint(language: str, occupation: str, company: str = "") -> str:
    lang = "de" if language == "gsw" else language
    if lang not in _HINT or not occupation:
        return ""
    return _HINT[lang].format(occupation=occupation, company=_AT[lang].format(company) if company else "")


# Whisper was trained on subtitles: on silence or noise it "hears" their typical last lines. In hands-free mode a
# silent recording became the answer "Danke.", the interviewer went on, the next silence gave "Danke." again: a loop.
_SUBTITLE_CREDITS = re.compile(
    # from the keyword to the end of the sentence; a dot inside a word ("Amara.org") does not end it
    r"(untertitel|copyright|sous-titr|sottotitol|amara\.org)([^.!?]|\.(?=\w))*[.!?]?",
    re.IGNORECASE)
_PHANTOM_WORDS = set(
    "danke dankeschön schön vielen dank fürs für zuschauen zuhören bis zum nächsten mal tschüss ciao "
    "merci beaucoup d'avoir regardé au revoir grazie mille per la visione arrivederci".split())


def drop_hallucinations(text: str) -> str:
    """The text without subtitle credits; "" if only a typical phantom line ("Danke.", "Vielen Dank fürs Zuschauen!")
    is left. A candidate who really only says "Danke." then has to say it again, which is harmless."""
    text = _SUBTITLE_CREDITS.sub("", text).strip()
    words = re.findall(r"[\w']+", text.lower())
    return "" if all(word in _PHANTOM_WORDS for word in words) else text


def transcribe(data: bytes, language: str, hint: str = "") -> dict:
    """The spoken text of a recording. Blocking (seconds on a CPU): call it in a thread.

    `hint`: words that may come up (vocabulary_hint), passed to Whisper as initial_prompt.
    """
    if not enabled():
        raise VoiceUnavailable("speech-to-text is switched off (STT_ENABLED=false)")
    audio = decode(data)
    seconds = len(audio) / SAMPLE_RATE
    if seconds > MAX_SECONDS:
        raise ValueError(f"audio is {seconds:.0f} s long, at most {MAX_SECONDS} s")
    name = model_name(language)
    model = load(name)
    started = time.monotonic()
    segments, _ = model.transcribe(
        audio,
        language="de" if language == "gsw" else language,
        vad_filter=True,  # skip silence: Whisper tends to invent text for silent parts
        condition_on_previous_text=False,
        initial_prompt=hint or None,
    )
    text = drop_hallucinations(" ".join(s.text.strip() for s in segments).strip())
    logger.info("transcribed %.1f s of %s in %.1f s", seconds, language, time.monotonic() - started)
    return {"text": text, "language": language, "duration_ms": round(seconds * 1000), "model": name.split("/")[-1]}
