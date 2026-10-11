// Audio for the server voice: playing the interviewer's voice (POST /speech) and recording the
// candidate's answer for Whisper (POST /transcribe). Both measure the loudness, which the call view
// animates (meter.speaker, meter.mic). The recorder also notices when the candidate stops speaking.

/** Current loudness 0 … 1. Updated about 60 times a second while audio plays or is recorded. */
export const meter = { speaker: 0, mic: 0 };

let context: AudioContext | null = null;

function audioContext(): AudioContext {
  context ??= new AudioContext();
  return context;
}

/**
 * Phones only allow sound after a tap. Call this in a click handler (e.g. the hands-free button),
 * then later playback works without a tap.
 */
export function unlockAudio() {
  const ctx = audioContext();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
}

/** Loudness of the analyser's current samples (root mean square), roughly 0 … 1. */
function loudness(analyser: AnalyserNode, samples: Float32Array<ArrayBuffer>) {
  analyser.getFloatTimeDomainData(samples);
  let sum = 0;
  for (const s of samples) sum += s * s;
  return Math.sqrt(sum / samples.length);
}

// ---------- playing ----------

export type Playback = { stop: () => void; done: Promise<void> };

/** Plays an audio file. `done` resolves when it has finished or was stopped. */
export async function play(audio: Blob): Promise<Playback> {
  const ctx = audioContext();
  if (ctx.state === "suspended") await ctx.resume().catch(() => {});
  const buffer = await ctx.decodeAudioData(await audio.arrayBuffer());

  const source = ctx.createBufferSource();
  source.buffer = buffer;
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser).connect(ctx.destination);

  const samples = new Float32Array(analyser.fftSize);
  let frame = 0;
  const measure = () => {
    // Speech is quiet in RMS terms; scale it so that normal speech moves the rings clearly
    meter.speaker = Math.min(1, loudness(analyser, samples) * 4);
    frame = requestAnimationFrame(measure);
  };

  const done = new Promise<void>((resolve) => {
    source.onended = () => {
      cancelAnimationFrame(frame);
      meter.speaker = 0;
      resolve();
    };
  });
  source.start();
  measure();
  return {
    stop: () => {
      try {
        source.stop();
      } catch {
        // already stopped
      }
    },
    done,
  };
}

// ---------- recording ----------

/** How the recorder decides that the candidate started and stopped speaking. */
const SPEECH_LEVEL = 0.02; // minimum loudness that counts as speech (above the room noise)
const MIN_SPEECH_MS = 300; // this much speech before a pause can end the answer

export type RecorderEvents = {
  /** The candidate has been quiet for `silenceMs` after speaking. */
  onSilence: () => void;
  /** Nothing was said for `idleMs` since the start. */
  onIdle: () => void;
};

export type Recording = {
  /** Stops and returns the recording (null if nothing was said). */
  stop: () => Promise<Blob | null>;
  /** Stops and throws the recording away. */
  cancel: () => void;
};

export const canRecord =
  typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices?.getUserMedia;

/** Starts recording from the microphone. Rejects with NotAllowedError if the candidate does not allow it. */
export async function record(silenceMs: number, idleMs: number, events: RecorderEvents): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const ctx = audioContext();
  if (ctx.state === "suspended") await ctx.resume().catch(() => {});

  // Safari records mp4, the others webm/opus; Whisper reads both
  const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.start(250);

  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  const input = ctx.createMediaStreamSource(stream);
  input.connect(analyser);
  const samples = new Float32Array(analyser.fftSize);

  const started = performance.now();
  let noise = 0.005; // room noise, learned while the candidate is quiet
  let speechMs = 0;
  let lastSpeech = 0;
  let last = started;
  let frame = 0;
  let finished = false;

  const measure = () => {
    const now = performance.now();
    const level = loudness(analyser, samples);
    meter.mic = Math.min(1, level * 6);
    const speaking = level > Math.max(SPEECH_LEVEL, noise * 3);
    if (speaking) {
      speechMs += now - last;
      lastSpeech = now;
    } else {
      noise = noise * 0.95 + level * 0.05;
    }
    last = now;
    if (speechMs >= MIN_SPEECH_MS && now - lastSpeech > silenceMs) events.onSilence();
    else if (speechMs < MIN_SPEECH_MS && now - started > idleMs) events.onIdle();
    else frame = requestAnimationFrame(measure);
  };
  measure();

  function release() {
    finished = true;
    cancelAnimationFrame(frame);
    meter.mic = 0;
    input.disconnect();
    stream.getTracks().forEach((track) => track.stop());
  }

  return {
    stop: () =>
      new Promise((resolve) => {
        if (finished) return resolve(null);
        const saidSomething = speechMs >= MIN_SPEECH_MS;
        recorder.onstop = () => resolve(saidSomething ? new Blob(chunks, { type: recorder.mimeType }) : null);
        recorder.stop();
        release();
      }),
    cancel: () => {
      if (finished) return;
      recorder.onstop = null;
      recorder.stop();
      release();
    },
  };
}
