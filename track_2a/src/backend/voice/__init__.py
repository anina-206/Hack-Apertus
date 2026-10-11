"""Server voice features: speech to text (stt.py, Whisper) and text to speech (tts.py, Piper or Azure).

Neither uses an LLM. Models are downloaded on first use into MODELS_DIR (data/models, a Docker volume).
"""

import os
from pathlib import Path

MODELS_DIR = Path(os.environ.get("MODELS_DIR") or Path(__file__).resolve().parents[3] / "data" / "models")


class VoiceUnavailable(Exception):
    """The feature is switched off, or its model could not be loaded (-> 503 VOICE_UNAVAILABLE)."""


def flag(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return default if not value else value not in ("0", "false", "off", "no")
