// Optional voice features of the browser: reading questions aloud and dictating answers.
// Both are hidden by the UI when the browser does not support them.

import type { LanguageCode } from "./api";

// Swiss German has no voice of its own, so it uses the (Swiss) German one.
const speechLang: Record<LanguageCode, string> = {
  de: "de-CH",
  fr: "fr-CH",
  it: "it-CH",
  gsw: "de-CH",
};

// ---------- text to speech ----------

export const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

// The browser loads its voices late, so we ask again when it says the list changed.
let voices: SpeechSynthesisVoice[] = [];
if (canSpeak) {
  const load = () => (voices = window.speechSynthesis.getVoices());
  load();
  window.speechSynthesis.addEventListener?.("voiceschanged", load);
}

/**
 * The best voice for a language: a Swiss one (de-CH) if there is one, then the main region
 * (de-DE, fr-FR, it-IT), then any voice of the language. Among those, the better sounding ones
 * (e.g. "Google", "Premium").
 */
export function pickVoice(language: LanguageCode, available = voices): SpeechSynthesisVoice | undefined {
  const wanted = speechLang[language].toLowerCase();
  const prefix = wanted.slice(0, 2);
  const quality = (v: SpeechSynthesisVoice) => {
    const lang = v.lang.toLowerCase().replace("_", "-");
    return (
      (lang === wanted ? 10 : lang === `${prefix}-${prefix}` ? 5 : 0) +
    (/google|premium|enhanced|natural|neural/i.test(v.name) ? 2 : 0) +
      (v.localService ? 0 : 1)
    );
  };
  return available
    .filter((v) => v.lang.toLowerCase().startsWith(prefix))
    .sort((a, b) => quality(b) - quality(a))[0];
}

/** Splits a text into sentences, because Chrome stops long utterances after about 15 seconds. */
export function sentences(text: string): string[] {
  return (text.match(/[^.!?…]+[.!?…]*["»«]*\s*/g) ?? [text]).map((s) => s.trim()).filter(Boolean);
}

/** Reads a text aloud. `onEnd` is called when it is finished or stopped. */
export function speak(text: string, language: LanguageCode, onEnd?: () => void) {
  if (!canSpeak) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const voice = pickVoice(language);
  const parts = sentences(text);
  parts.forEach((part, i) => {
    const utterance = new SpeechSynthesisUtterance(part);
    utterance.lang = voice?.lang ?? speechLang[language];
    if (voice) utterance.voice = voice;
    utterance.rate = 0.95; // a little slower than normal, easier to follow
    if (i === parts.length - 1) {
      utterance.onend = () => onEnd?.();
      utterance.onerror = () => onEnd?.();
    }
    window.speechSynthesis.speak(utterance);
  });
}

export function stopSpeaking() {
  if (canSpeak) window.speechSynthesis.cancel();
}

// ---------- speech to text ----------

// The browser API is not in TypeScript's DOM types, so we describe the small part we use.
type RecognitionResultEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
};

const RecognitionClass: (new () => Recognition) | undefined =
  typeof window === "undefined"
    ? undefined
    : (window as unknown as { SpeechRecognition?: new () => Recognition }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: new () => Recognition }).webkitSpeechRecognition;

export const canListen = RecognitionClass !== undefined;

/** Why dictation stopped: normally (null), no microphone permission, nothing understood, or another problem. */
export type ListenError = "not-allowed" | "nothing" | "other" | null;

/**
 * Starts dictation. `onText` gets everything spoken so far, `onEnd` is called when it stops.
 * Returns a function that stops it.
 */
export function startListening(
  language: LanguageCode,
  onText: (spoken: string) => void,
  onEnd: (error: ListenError) => void,
): () => void {
  if (!RecognitionClass) {
    onEnd("other");
    return () => {};
  }
  const recognition = new RecognitionClass();
  recognition.lang = speechLang[language];
  recognition.continuous = true;
  recognition.interimResults = true;
  let error: ListenError = null;
  recognition.onresult = (event) => {
    const spoken = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(" ")
      .trim();
    onText(spoken);
  };
  recognition.onerror = (event) => {
    // "no-speech" and "aborted" are normal: nothing was said, or we stopped it ourselves
    if (event.error === "not-allowed" || event.error === "service-not-allowed") error = "not-allowed";
    else if (event.error !== "no-speech" && event.error !== "aborted") error = "other";
  };
  recognition.onend = () => onEnd(error);
  try {
    recognition.start();
  } catch {
    onEnd("other");
  }
  return () => recognition.stop();
}
