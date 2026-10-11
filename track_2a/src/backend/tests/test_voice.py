"""Voice endpoints (POST /transcribe, POST /speech) with fake models: no Whisper or Piper is loaded."""

from types import SimpleNamespace

import pytest

from backend import config
from backend.voice import stt, tts
from backend.tests.test_graph import SETUP, api, fake, start  # noqa: F401  (fixtures)

WAV = b"RIFF fake audio"


@pytest.fixture
def whisper(monkeypatch):
    """Fake Whisper: 3 s of audio, says "Ich baue gerne PCs." and remembers the language it got."""
    seen = {}

    class Model:
        def transcribe(self, audio, language, **_):
            seen["language"] = language
            return iter([SimpleNamespace(text=" Ich baue"), SimpleNamespace(text=" gerne PCs. ")]), None

    monkeypatch.setattr(stt, "decode", lambda data: [0.0] * (3 * stt.SAMPLE_RATE))
    monkeypatch.setattr(stt, "load", lambda name: seen.setdefault("model", name) and Model())
    return seen


def test_transcribe(api, whisper):
    resp = api.post("/api/v1/transcribe", files={"audio": ("a.webm", WAV, "audio/webm")}, data={"language": "gsw"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"text": "Ich baue gerne PCs.", "language": "gsw", "duration_ms": 3000,
                           "model": "whisper-large-v3-turbo-swiss-german-ct2-int8"}
    assert whisper["language"] == "de"  # Whisper knows Swiss German as "de"


def test_transcribe_uses_the_multilingual_model_for_french(api, whisper):
    api.post("/api/v1/transcribe", files={"audio": ("a.webm", WAV, "audio/webm")}, data={"language": "fr"})
    assert whisper == {"model": "large-v3-turbo", "language": "fr"}


def test_transcribe_errors(api, whisper, monkeypatch):
    def post(data=WAV, language="de"):
        resp = api.post("/api/v1/transcribe", files={"audio": ("a.webm", data, "audio/webm")}, data={"language": language})
        return resp.status_code, resp.json()["error"]["code"]

    assert post(language="en") == (400, "INVALID_REQUEST")
    assert post(data=b"") == (400, "INVALID_REQUEST")
    assert post(data=b"x" * (5 * 1024 * 1024 + 1)) == (400, "INVALID_REQUEST")
    monkeypatch.setattr(stt, "decode", lambda data: [0.0] * (61 * stt.SAMPLE_RATE))
    assert post() == (400, "INVALID_REQUEST")  # longer than 60 s
    monkeypatch.setenv("STT_ENABLED", "false")
    assert post() == (503, "VOICE_UNAVAILABLE")


def test_speech_with_piper(api, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "_piper_speech", lambda text, language, voice: calls.append((text, voice)) or b"RIFFwav")
    tts.speech.cache_clear()
    resp = api.post("/api/v1/speech", json={"text": " Grüezi! ", "language": "gsw", "voice": "male"})
    assert resp.status_code == 200 and resp.content == b"RIFFwav"
    assert resp.headers["content-type"] == "audio/wav" and resp.headers["x-tts-engine"] == "piper"
    api.post("/api/v1/speech", json={"text": "Grüezi!", "language": "gsw", "voice": "male"})
    assert calls == [("Grüezi!", "male")]  # the second time comes from the cache


def test_speech_errors(api, monkeypatch):
    assert api.post("/api/v1/speech", json={"text": "", "language": "de"}).status_code == 400
    assert api.post("/api/v1/speech", json={"text": "Hallo", "language": "de", "voice": "robot"}).status_code == 400
    monkeypatch.setenv("TTS_ENGINE", "off")
    tts.speech.cache_clear()
    resp = api.post("/api/v1/speech", json={"text": "Hallo", "language": "de"})
    assert resp.status_code == 503 and resp.json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_engine_choice(monkeypatch):
    monkeypatch.delenv("TTS_ENGINE", raising=False)
    assert tts.engine() == "piper"
    monkeypatch.setenv("TTS_ENGINE", "azure")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    assert tts.engine() == "piper"  # no key: stays local
    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    assert tts.engine() == "azure"


def test_config_and_interviewer_voice(api, fake, monkeypatch):
    fake()
    monkeypatch.setenv("STT_ENABLED", "false")
    monkeypatch.setenv("TTS_ENGINE", "off")
    assert api.get("/api/v1/config").json()["voice"] == {"stt": False, "tts": None}
    assert start(api, posting_id="P-11")["interviewer"]["voice"] == "male"  # Berufsbildner
    assert start(api, posting_id="P-03")["interviewer"]["voice"] == "female"  # HR-Fachfrau
    assert config.interviewer_voice(None) == "female"


def test_every_posting_has_a_voice():
    voices = config._interviewer_voices()
    assert sorted(voices["female"] + voices["male"]) == sorted(config.postings())


def test_voice_of_a_contact_person_from_the_letter():
    assert config.contact_voice("Frau Keller", "") == "female"
    assert config.contact_voice("Herr Brunner", "Berufsbildner") == "male"
    assert config.contact_voice("Madame Roux", "") == "female"
    assert config.contact_voice("Luca Rossi", "formatore") == "male"  # from the role
    assert config.contact_voice("Andrea Meier", "Berufsbildnerin, Logistik") == "female"
    assert config.contact_voice("Sam Keller", "") == "female"  # nothing to go by: the default
