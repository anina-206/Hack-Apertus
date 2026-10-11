// Voice for the interview screen: reading aloud, dictation and the hands-free mode.
//
// Hands-free mode is a small loop:
//   read the question aloud -> listen -> pause in speech -> send the answer -> next question ...
// - After the last spoken word, a short countdown runs (SILENCE_MS). New words restart it.
// - When the browser stops the microphone by itself (pause, time limit), it is started again.
// - Saying "nochmal" / "répète" / "ripeti" instead of an answer reads the question again.

import { useEffect, useRef, useState } from "react";
import type { LanguageCode } from "./api";
import { canListen, canSpeak, speak, startListening, stopSpeaking, type ListenError } from "./speech";

/** Pause after the last spoken word before hands-free mode sends the answer. */
export const SILENCE_MS = 3000;
/** Microphone restarts in a row without hearing anything before hands-free mode waits for a tap. */
const MAX_QUIET_RESTARTS = 3;

/** An answer that only asks to hear the question again. */
const REPEAT =
  /^(bitte |s'il te plaît |per favore )?(nochmal|nochmals|nomal|nomol|wiederholen|wie bitte|répète|répéter|répétez|encore une fois|pardon|ripeti|ripetere|di nuovo|come)( bitte| s'il te plaît| s'il vous plaît| per favore)?[.!?]?$/i;

export function isRepeatRequest(answer: string) {
  return REPEAT.test(answer.trim());
}

type Options = {
  language: LanguageCode;
  draft: string;
  setDraft: (text: string) => void;
  /** Hands-free mode sends the answer itself after a pause */
  onSend: (answer: string) => void;
  /** Hands-free mode: the candidate asked to hear the question again */
  onRepeat: () => void;
};

export function useVoice({ language, draft, setDraft, onSend, onRepeat }: Options) {
  const [handsFree, setHandsFree] = useState(() => canSpeak && loadHandsFree());
  /** Key of the text that is being read aloud (the message index), or null */
  const [speakingKey, setSpeakingKey] = useState<number | null>(null);
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState<ListenError>(null);
  /** Hands-free mode stopped listening and waits for a tap on the microphone */
  const [paused, setPaused] = useState(false);
  /** Hands-free countdown after the last word: 0 … 1, null when it does not run */
  const [countdown, setCountdown] = useState<number | null>(null);

  // The speech callbacks run later, so they read the current values from here
  const latest = useRef({ language, draft, handsFree, onSend, onRepeat });
  latest.current = { language, draft, handsFree, onSend, onRepeat };

  const stopRecognition = useRef<(() => void) | null>(null);
  const stoppedByUs = useRef(false);
  const quietRestarts = useRef(0);
  const lastWordAt = useRef(0);
  const timer = useRef<number | null>(null);
  // Counts readings. Stopping speech also calls its "finished" callback, so the callback only
  // acts if its reading is still the current one.
  const reading = useRef(0);

  // ---------- countdown ----------

  function stopCountdown() {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    setCountdown(null);
  }

  function restartCountdown() {
    lastWordAt.current = Date.now();
    if (timer.current !== null) return;
    timer.current = window.setInterval(() => {
      const elapsed = (Date.now() - lastWordAt.current) / SILENCE_MS;
      if (elapsed < 1) setCountdown(elapsed);
      else finishAnswer();
    }, 100);
  }

  function finishAnswer() {
    const answer = latest.current.draft.trim();
    stopMic();
    if (!answer) return;
    if (isRepeatRequest(answer)) {
      setDraft("");
      latest.current.onRepeat();
    } else {
      latest.current.onSend(answer);
    }
  }

  // ---------- microphone ----------

  function startMic() {
    if (!canListen || stopRecognition.current) return;
    stopReading();
    stoppedByUs.current = false;
    setPaused(false);
    setMicError(null);
    setListening(true);
    // Dictated text is added to what is already in the input field
    const base = latest.current.draft.trim();
    stopRecognition.current = startListening(
      latest.current.language,
      (spoken) => {
        setDraft(base ? `${base} ${spoken}` : spoken);
        quietRestarts.current = 0;
        if (latest.current.handsFree) restartCountdown();
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
        startMic();
      },
    );
  }

  function stopMic() {
    stoppedByUs.current = true;
    stopCountdown();
    stopRecognition.current?.();
  }

  function toggleMic() {
    if (listening) stopMic();
    else startMic();
  }

  /** Hands-free: stop reading, listening and auto-sending, e.g. because the candidate wants to type. */
  function hold() {
    if (!latest.current.handsFree || (!stopRecognition.current && speakingKey === null)) return;
    stopReading();
    stopMic();
    setPaused(true);
  }

  // ---------- reading aloud ----------

  /** Reads a text aloud. With `thenListen`, the microphone starts when reading is done. */
  function say(key: number, text: string, thenListen = false) {
    stopMic();
    const current = ++reading.current;
    setSpeakingKey(key);
    speak(text, latest.current.language, () => {
      if (reading.current !== current) return; // stopped or replaced by a newer reading
      setSpeakingKey(null);
      if (thenListen) startMic();
    });
  }

  function stopReading() {
    reading.current++;
    setSpeakingKey(null);
    stopSpeaking();
  }

  /** Hands-free: skip the rest of the reading and start listening. */
  function skipReading() {
    stopReading();
    if (latest.current.handsFree) startMic();
  }

  // ---------- hands-free switch ----------

  /** Switches hands-free mode and returns the new state. */
  function toggleHandsFree() {
    const on = !handsFree;
    setHandsFree(on);
    latest.current.handsFree = on;
    saveHandsFree(on);
    if (!on) stopAll();
    return on;
  }

  function stopAll() {
    stopReading();
    stopMic();
    setPaused(false);
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
    toggleMic,
    startMic,
    stopMic,
    hold,
    paused,
    countdown,
    micError,
    stopAll,
  };
}

// The hands-free switch is remembered in this browser. Storage can be blocked, so both are guarded.
const HANDS_FREE_KEY = "coach.handsFree";

function loadHandsFree() {
  try {
    return localStorage.getItem(HANDS_FREE_KEY) === "on";
  } catch {
    return false;
  }
}

function saveHandsFree(on: boolean) {
  try {
    localStorage.setItem(HANDS_FREE_KEY, on ? "on" : "off");
  } catch {
    // not saved, the switch still works for this interview
  }
}
