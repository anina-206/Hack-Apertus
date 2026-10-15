// Voice for the interview screen: reading aloud, dictation and the hands-free mode.
//
// Two engines, chosen by what the backend offers (GET /config -> voice):
// - server: the interviewer speaks with Piper/Azure (POST /speech), answers are recorded and
//   transcribed by Whisper (POST /transcribe). Both give real loudness for the animation (audio.ts).
// - browser: speechSynthesis and SpeechRecognition (speech.ts), used when the server has no voice,
//   in the mock, or when a server voice call fails.
//
// Hands-free mode is a loop:
//   read the question aloud -> listen -> pause in speech -> (transcribe) -> short countdown -> send
// - New words (browser) or "Warten" stop the countdown. Tapping the input field pauses everything.
// - Saying "nochmal" / "répète" / "ripeti" instead of an answer reads the question again.

import { useEffect, useRef, useState } from "react";
import { api, type AppConfig, type LanguageCode, type Voice } from "./api";
import { canRecord, play, record, unlockAudio, type Playback, type Recording } from "./audio";
import { canListen, speak, speechChunks, startListening, stopSpeaking, type ListenError } from "./speech";

/** Browser engine: pause after the last recognised word before the answer is sent (long enough to think mid-answer). */
export const SILENCE_MS = 4500;
/** Server engine: pause that ends the recording, then the countdown before sending. */
const RECORD_PAUSE_MS = { handsFree: 2000, manual: 2500 };
const CONFIRM_MS = 3500;
/** Server engine: stop recording if nothing is said for this long. */
const IDLE_MS = 12000;
/** Browser engine: microphone restarts in a row without hearing anything before hands-free waits for a tap. */
const MAX_QUIET_RESTARTS = 3;

/** An answer that only asks to hear the question again. */
const REPEAT =
  /^(bitte |s'il te plaît |per favore )?(nochmal|nochmals|nomal|nomol|wiederholen|wie bitte|répète|répéter|répétez|encore une fois|pardon|ripeti|ripetere|di nuovo|come)( bitte| s'il te plaît| s'il vous plaît| per favore)?[.!?]?$/i;

export function isRepeatRequest(answer: string) {
  return REPEAT.test(answer.trim());
}

// What the backend offers, asked once (GET /config is small and already loaded by the setup screen)
type ServerVoice = NonNullable<AppConfig["voice"]>;
let serverVoice: Promise<ServerVoice> | null = null;
function loadServerVoice(): Promise<ServerVoice> {
  serverVoice ??= api
    .getConfig()
    .then((c) => c.voice ?? { stt: false, tts: null })
    .catch(() => ({ stt: false, tts: null }));
  return serverVoice;
}

type Options = {
  language: LanguageCode;
  /** Lets Whisper know the occupation and company, so it gets their words right */
  sessionId?: string;
  /** The interviewer's voice for POST /speech */
  voice: Voice;
  draft: string;
  setDraft: (text: string) => void;
  /** Hands-free mode sends the answer itself after a pause */
  onSend: (answer: string) => void;
  /** Hands-free mode: the candidate asked to hear the question again */
  onRepeat: () => void;
};

export function useVoice({ language, sessionId, voice, draft, setDraft, onSend, onRepeat }: Options) {
  // Off at the start of every interview: nothing is read aloud or recorded until the candidate taps the button
  const [handsFree, setHandsFree] = useState(false);
  /** Key of the text that is being read aloud (the message index), or null */
  const [speakingKey, setSpeakingKey] = useState<number | null>(null);
  const [listening, setListening] = useState(false);
  /** Server engine: Whisper is working on the recording */
  const [transcribing, setTranscribing] = useState(false);
  const [micError, setMicError] = useState<ListenError>(null);
  /** Hands-free mode stopped listening and waits for a tap on the microphone */
  const [paused, setPaused] = useState(false);
  /** Hands-free countdown before sending: 0 … 1, null when it does not run */
  const [countdown, setCountdown] = useState<number | null>(null);
  /** Which engines are in use (the call view animates real loudness only for the server ones) */
  const [server, setServer] = useState<{ stt: boolean; tts: boolean }>({ stt: false, tts: false });

  // The speech callbacks run later, so they read the current values from here
  const latest = useRef({ language, sessionId, voice, draft, handsFree, onSend, onRepeat });
  latest.current = { language, sessionId, voice, draft, handsFree, onSend, onRepeat };

  const stopRecognition = useRef<(() => void) | null>(null); // browser engine
  const recording = useRef<Recording | null>(null); // server engine
  const playback = useRef<Playback | null>(null);
  const stoppedByUs = useRef(false);
  const quietRestarts = useRef(0);
  const lastWordAt = useRef(0);
  const timer = useRef<number | null>(null);
  /** "Senden" was tapped while the recording was still being transcribed: send as soon as the text is there */
  const sendWhenWritten = useRef(false);
  // Counters for readings and recordings. Stopping also triggers their "finished" callbacks,
  // so a callback only acts if its reading / recording is still the current one.
  const reading = useRef(0);
  const listenRound = useRef(0);

  useEffect(() => {
    loadServerVoice().then((v) => setServer({ stt: v.stt && canRecord, tts: !!v.tts }));
  }, []);

  // ---------- countdown before sending ----------

  function stopCountdown() {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    setCountdown(null);
  }

  /** Runs the countdown; `durationMs` after the last call (new words restart it), the answer is sent. */
  function restartCountdown(durationMs: number) {
    lastWordAt.current = Date.now();
    if (timer.current !== null) return;
    timer.current = window.setInterval(() => {
      const elapsed = (Date.now() - lastWordAt.current) / durationMs;
      if (elapsed < 1) setCountdown(elapsed);
      else finishAnswer();
    }, 50);
  }

  function finishAnswer() {
    const answer = latest.current.draft.trim();
    stopMic();
    deliver(answer);
  }

  function deliver(answer: string) {
    if (!answer) {
      // "Senden" before anything was said: hands-free waits for a tap instead of standing still
      if (latest.current.handsFree) setPaused(true);
      return;
    }
    if (isRepeatRequest(answer)) {
      setDraft("");
      latest.current.onRepeat();
    } else {
      latest.current.onSend(answer);
    }
  }

  /**
   * "Senden": send the spoken answer now instead of waiting for a pause or the countdown.
   * A running recording is stopped and transcribed first, then sent right away.
   */
  function sendNow() {
    unlockAudio();
    if (recording.current || transcribing) {
      sendWhenWritten.current = true;
      if (recording.current) finishRecording();
      return;
    }
    finishAnswer();
  }

  // ---------- microphone ----------

  async function startMic() {
    if (stopRecognition.current || recording.current) return;
    stopReading();
    stoppedByUs.current = false;
    setPaused(false);
    setMicError(null);
    const { stt } = await loadServerVoice();
    if (stt && canRecord) await startRecording();
    else startBrowserListening();
  }

  /** Server engine: record until a pause, then let Whisper write it down. */
  async function startRecording() {
    const round = ++listenRound.current;
    const pause = latest.current.handsFree ? RECORD_PAUSE_MS.handsFree : RECORD_PAUSE_MS.manual;
    setListening(true);
    try {
      const rec = await record(pause, IDLE_MS, {
        onSilence: () => finishRecording(round),
        // No speech noticed for a while: the microphone may just be quiet, so let Whisper listen anyway
        onIdle: () => finishRecording(round),
      });
      if (round !== listenRound.current) return rec.cancel(); // stopped while the microphone was starting
      recording.current = rec;
    } catch (error) {
      setListening(false);
      setMicError(error instanceof DOMException && error.name === "NotAllowedError" ? "not-allowed" : "other");
    }
  }

  async function finishRecording(round = listenRound.current) {
    const rec = recording.current;
    if (!rec || round !== listenRound.current) return;
    recording.current = null;
    setListening(false);
    const audio = await rec.stop();
    if (!audio) {
      sendWhenWritten.current = false;
      setMicError("nothing");
      if (latest.current.handsFree) setPaused(true);
      return;
    }
    setTranscribing(true);
    try {
      const { text } = await api.transcribe(audio, latest.current.language, latest.current.sessionId);
      if (round !== listenRound.current) return; // stopped in the meantime
      const base = latest.current.draft.trim();
      if (!text.trim()) {
        sendWhenWritten.current = false;
        setMicError("nothing");
        if (latest.current.handsFree) setPaused(true);
        return;
      }
      const answer = base ? `${base} ${text.trim()}` : text.trim();
      setDraft(answer);
      if (sendWhenWritten.current) {
        sendWhenWritten.current = false;
        deliver(answer);
      } else if (latest.current.handsFree) {
        restartCountdown(CONFIRM_MS);
      }
    } catch {
      sendWhenWritten.current = false;
      setMicError("other");
      // Whisper is not available: use the browser's recognition from now on
      setServer((s) => ({ ...s, stt: false }));
      serverVoice = loadServerVoice().then((v) => ({ ...v, stt: false }));
    } finally {
      setTranscribing(false);
    }
  }

  /** Browser engine: live recognition, the countdown starts after the last word. */
  function startBrowserListening() {
    if (!canListen) return;
    const round = ++listenRound.current;
    setListening(true);
    // Dictated text is added to what is already in the input field
    const base = latest.current.draft.trim();
    stopRecognition.current = startListening(
      latest.current.language,
      (spoken) => {
        // After stop() the browser still delivers the last result. Without this check, an answer that was
        // already sent came back into the input field and the next answer was added to it.
        if (round !== listenRound.current) return;
        setDraft(base ? `${base} ${spoken}` : spoken);
        quietRestarts.current = 0;
        if (latest.current.handsFree) restartCountdown(SILENCE_MS);
      },
      (problem) => {
        stopRecognition.current = null;
        setListening(false);
        if (problem) {
          stopCountdown();
          setMicError(problem);
          return;
        }
        if (stoppedByUs.current || !latest.current.handsFree) {
          stopCountdown();
          return;
        }
        // The browser stopped by itself: listen again, unless nothing was heard several times
        if (timer.current === null) quietRestarts.current += 1;
        if (quietRestarts.current > MAX_QUIET_RESTARTS) {
          quietRestarts.current = 0;
          setPaused(true);
          return;
        }
        startBrowserListening();
      },
    );
  }

  function stopMic() {
    stoppedByUs.current = true;
    sendWhenWritten.current = false;
    listenRound.current++;
    stopCountdown();
    stopRecognition.current?.();
    recording.current?.cancel();
    recording.current = null;
    setListening(false);
    setTranscribing(false);
  }

  function toggleMic() {
    unlockAudio();
    if (recording.current) finishRecording();
    else if (listening) stopMic();
    else startMic();
  }

  /** Hands-free: stop reading, listening and sending, e.g. because the candidate wants to type. */
  function hold() {
    const busy = stopRecognition.current || recording.current || transcribing || speakingKey !== null || countdown !== null;
    if (!latest.current.handsFree || !busy) return;
    stopReading();
    stopMic();
    setPaused(true);
  }

  // ---------- reading aloud ----------

  /** Reads a text aloud. With `thenListen`, the microphone starts when reading is done. */
  async function say(key: number, text: string, thenListen = false) {
    unlockAudio(); // still inside the tap on "Vorlesen": later, after loading the audio, it would be too late
    stopMic();
    const current = ++reading.current;
    setSpeakingKey(key);
    const { tts } = await loadServerVoice();
    // Sentence by sentence: the first one plays while the server makes the next one
    const chunks = speechChunks(text);
    let done = 0; // chunks already played
    const load = (i: number) => {
      const audio = api.speech(chunks[i], latest.current.language, latest.current.voice);
      audio.catch(() => {}); // handled when it is awaited; avoids a warning if reading stops first
      return audio;
    };
    try {
      let next = tts && chunks.length ? load(0) : null;
      while (next) {
        const audio = await next;
        if (reading.current !== current) return;
        next = done + 1 < chunks.length ? load(done + 1) : null;
        playback.current = await play(audio);
        await playback.current.done;
        if (reading.current !== current) return;
        done++;
      }
    } catch {
      // server voice failed: the browser reads the rest instead
    }
    // Without a server voice (or after it failed) the browser reads what is left
    if (done < chunks.length && reading.current === current) {
      await new Promise<void>((resolve) => speak(chunks.slice(done).join(" "), latest.current.language, resolve));
    }
    if (reading.current !== current) return; // stopped or replaced by a newer reading
    playback.current = null;
    setSpeakingKey(null);
    if (thenListen) startMic();
  }

  function stopReading() {
    reading.current++;
    playback.current?.stop();
    playback.current = null;
    setSpeakingKey(null);
    stopSpeaking();
  }

  /** Hands-free: skip the rest of the reading and start listening. */
  function skipReading() {
    stopReading();
    if (latest.current.handsFree) startMic();
  }

  // ---------- hands-free switch ----------

  /** Switches hands-free mode and returns the new state. Call it from a click (unlocks audio on phones). */
  function toggleHandsFree() {
    unlockAudio();
    const on = !handsFree;
    setHandsFree(on);
    latest.current.handsFree = on;
    if (!on) stopAll();
    return on;
  }

  /** Hands-free: continue after a pause. */
  function resume() {
    unlockAudio();
    setPaused(false);
    startMic();
  }

  function stopAll() {
    stopReading();
    stopMic();
    setPaused(false);
    setMicError(null);
  }

  /** Hides the microphone message (× on it, or the candidate starts typing). */
  function dismissMicError() {
    setMicError(null);
  }

  // Stop everything when the screen closes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => stopAll, []);

  // Keep the phone screen on during hands-free mode (where the browser allows it)
  useEffect(() => {
    if (!handsFree || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let cancelled = false;
    navigator.wakeLock
      .request("screen")
      .then((l) => {
        if (cancelled) l.release();
        else lock = l;
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      lock?.release().catch(() => {});
    };
  }, [handsFree]);

  return {
    handsFree,
    toggleHandsFree,
    speakingKey,
    say,
    stopReading,
    skipReading,
    listening,
    transcribing,
    toggleMic,
    sendNow,
    startMic,
    stopMic,
    hold,
    resume,
    paused,
    countdown,
    micError,
    dismissMicError,
    stopAll,
    /** True when the server engines are used (real loudness in audio.ts meter) */
    server,
  };
}
