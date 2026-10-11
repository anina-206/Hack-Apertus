"""Text to speech for the interviewer's lines: POST /api/v1/speech.

TTS_ENGINE chooses the engine:
- piper (default): open source, runs on the CPU in the backend, nothing leaves the server.
  Standard German / French / Italian voices (Piper has no Swiss voices).
- azure: Microsoft Azure neural voices with a Swiss accent (de-CH, fr-CH; Italian: it-IT).
  Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (e.g. switzerlandnorth). The text is sent to Azure.
- off: no server voice; the frontend reads aloud with the browser's voice.
Mundart (gsw) is read with the German voice.
"""

import io
import logging
import os
import threading
import time
import wave
from functools import lru_cache
from xml.sax.saxutils import escape

import httpx

from backend.voice import MODELS_DIR, VoiceUnavailable

logger = logging.getLogger("voice.tts")

VOICES = ("female", "male")
MAX_CHARS = 1000

# Piper voices (https://huggingface.co/rhasspy/piper-voices): "<language>_<REGION>-<name>-<quality>"
PIPER_VOICES = {
    ("de", "female"): "de_DE-kerstin-low",
    ("de", "male"): "de_DE-thorsten-high",
    ("fr", "female"): "fr_FR-siwis-medium",
    ("fr", "male"): "fr_FR-tom-medium",
    ("it", "female"): "it_IT-serena-high",
    ("it", "male"): "it_IT-riccardo-x_low",
}

AZURE_VOICES = {
    ("de", "female"): "de-CH-LeniNeural",
    ("de", "male"): "de-CH-JanNeural",
    ("fr", "female"): "fr-CH-ArianeNeural",
    ("fr", "male"): "fr-CH-FabriceNeural",
    ("it", "female"): "it-IT-ElsaNeural",
    ("it", "male"): "it-IT-DiegoNeural",
}

_piper: dict = {}
_lock = threading.Lock()


def engine() -> str | None:
    """"piper", "azure" or None (off)."""
    name = (os.environ.get("TTS_ENGINE") or "piper").strip().lower()
    if name == "azure" and os.environ.get("AZURE_SPEECH_KEY"):
        return "azure"
    if name == "azure":
        logger.warning("TTS_ENGINE=azure but AZURE_SPEECH_KEY is not set: using piper")
    return None if name in ("off", "false", "none", "0") else "piper"


def _base(language: str) -> str:
    return "de" if language == "gsw" else language


# ---------- Piper ----------

def _piper_voice(name: str):
    """A Piper voice, downloaded (about 60 MB) and loaded on first use. Thread-safe."""
    with _lock:
        if name not in _piper:
            from huggingface_hub import hf_hub_download
            from piper import PiperVoice

            started = time.monotonic()
            lang_region, speaker, quality = name.split("-")
            path = f"{lang_region.split('_')[0]}/{lang_region}/{speaker}/{quality}/{name}.onnx"
            folder = MODELS_DIR / "piper"
            try:
                model = hf_hub_download("rhasspy/piper-voices", path, local_dir=folder)
                hf_hub_download("rhasspy/piper-voices", path + ".json", local_dir=folder)
                _piper[name] = PiperVoice.load(model)
            except Exception as exc:
                logger.exception("Piper voice could not be loaded")
                raise VoiceUnavailable(f"voice {name} could not be loaded: {exc}") from exc
            logger.info("piper voice %s loaded in %.1f s", name, time.monotonic() - started)
        return _piper[name]


def _piper_speech(text: str, language: str, voice: str) -> bytes:
    from piper import SynthesisConfig

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        # length_scale > 1 speaks a little slower: easier to follow for the candidate
        _piper_voice(PIPER_VOICES[(_base(language), voice)]).synthesize_wav(
            text, wav, syn_config=SynthesisConfig(length_scale=1.08))
    return buffer.getvalue()


# ---------- Azure ----------

def _azure_speech(text: str, language: str, voice: str) -> bytes:
    name = AZURE_VOICES[(_base(language), voice)]
    region = os.environ.get("AZURE_SPEECH_REGION") or "switzerlandnorth"
    ssml = (f"<speak version='1.0' xml:lang='{name[:5]}'><voice name='{name}'>"
            f"<prosody rate='-5%'>{escape(text)}</prosody></voice></speak>")
    try:
        response = httpx.post(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            content=ssml.encode("utf-8"), timeout=20,
            headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                     "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                     "User-Agent": "schnupper-interview-coach"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise VoiceUnavailable(f"Azure speech failed: {exc}") from exc
    return response.content


# ---------- both ----------

def preload() -> None:
    """Load the Piper voices at startup, so that the first question is read without delay."""
    if engine() != "piper":
        return
    for name in PIPER_VOICES.values():
        try:
            _piper_voice(name)
        except VoiceUnavailable:
            pass  # already logged


@lru_cache(maxsize=128)  # the same question is often read twice ("nochmal")
def speech(text: str, language: str, voice: str = "female") -> tuple[bytes, str, str]:
    """(audio, media type, engine) for a text. Blocking: call it in a thread."""
    current = engine()
    if current is None:
        raise VoiceUnavailable("text-to-speech is switched off (TTS_ENGINE=off)")
    started = time.monotonic()
    if current == "azure":
        audio, media_type = _azure_speech(text, language, voice), "audio/mpeg"
    else:
        audio, media_type = _piper_speech(text, language, voice), "audio/wav"
    logger.info("%s speech for %d characters in %.2f s", current, len(text), time.monotonic() - started)
    return audio, media_type, current
