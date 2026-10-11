// Fake backend that runs in the browser.
// Same behaviour as track_2a/docs/api.md, but with fixed questions and random scores.

import type { InterviewApi } from "./InterviewApi";
import {
  ApiError,
  type AnswerResponse,
  type AppConfig,
  type AuthResponse,
  type CreateSessionRequest,
  type CriterionId,
  type HistoryEntry,
  type User,
  type LanguageCode,
  type Phase,
  type Report,
  type Scores,
  type SessionState,
} from "./types";

const config: AppConfig = {
  languages: [
    { code: "de", label: "Deutsch" },
    { code: "fr", label: "Français" },
    { code: "it", label: "Italiano" },
    { code: "gsw", label: "Schwiizerdütsch (Beta)" },
  ],
  occupations: [
    { id: "schreiner_efz", label: { de: "Schreiner/in EFZ", fr: "Menuisier/ère CFC", it: "Falegname/a AFC" } },
    { id: "informatiker_efz", label: { de: "Informatiker/in EFZ", fr: "Informaticien/ne CFC", it: "Informatico/a AFC" } },
    { id: "kv_efz", label: { de: "Kaufmann/-frau EFZ", fr: "Employé/e de commerce CFC", it: "Impiegato/a di commercio AFC" } },
    { id: "fage_efz", label: { de: "Fachmann/-frau Gesundheit EFZ", fr: "Assistant/e en soins et santé communautaire CFC", it: "Operatore/trice sociosanitario/a AFC" } },
  ],
  interviewer_styles: [
    { id: "friendly", label: { de: "Freundlich", fr: "Bienveillant", it: "Cordiale" } },
    { id: "strict", label: { de: "Streng", fr: "Exigeant", it: "Esigente" } },
  ],
  modes: [
    { id: "training", description: "Short feedback after every answer" },
    { id: "rehearsal", description: "Realistic, feedback only at the end" },
  ],
};

// 8 questions per language, in interview order. "{name}" is replaced by the first name.
const script: { phase: Phase; text: Record<LanguageCode, string> }[] = [
  {
    phase: "intro",
    text: {
      de: "Grüezi{name}! Erzähl mir doch zuerst etwas über dich.",
      fr: "Bonjour{name} ! Parle-moi d'abord un peu de toi.",
      it: "Buongiorno{name}! Raccontami prima qualcosa di te.",
      gsw: "Grüezi{name}! Verzell mer doch zersch chli öppis über dich.",
    },
  },
  {
    phase: "motivation",
    text: {
      de: "Wie bist du auf diesen Beruf gekommen?",
      fr: "Comment as-tu découvert ce métier ?",
      it: "Come hai scoperto questa professione?",
      gsw: "Wie bisch du uf dä Bruef cho?",
    },
  },
  {
    phase: "motivation",
    text: {
      de: "Warum möchtest du die Lehre gerade bei uns machen?",
      fr: "Pourquoi veux-tu faire ton apprentissage chez nous ?",
      it: "Perché vuoi fare l'apprendistato proprio da noi?",
      gsw: "Wieso wotsch du d Lehr grad bi üs mache?",
    },
  },
  {
    phase: "strengths_weaknesses",
    text: {
      de: "Was sind deine grössten Stärken?",
      fr: "Quels sont tes plus grands points forts ?",
      it: "Quali sono i tuoi punti di forza più grandi?",
      gsw: "Was sind dini gröschte Stärche?",
    },
  },
  {
    phase: "strengths_weaknesses",
    text: {
      de: "Und woran möchtest du noch arbeiten?",
      fr: "Et sur quoi aimerais-tu encore travailler ?",
      it: "E su cosa vorresti ancora lavorare?",
      gsw: "Und a was wotsch du no schaffe?",
    },
  },
  {
    phase: "situational",
    text: {
      de: "Stell dir vor, du machst bei der Arbeit einen Fehler. Was tust du?",
      fr: "Imagine que tu fais une erreur au travail. Que fais-tu ?",
      it: "Immagina di fare un errore al lavoro. Cosa fai?",
      gsw: "Stell der vor, du machsch bim Schaffe en Fehler. Was machsch du?",
    },
  },
  {
    phase: "situational",
    text: {
      de: "Erzähl von einer Situation, in der du im Team gearbeitet hast.",
      fr: "Raconte une situation où tu as travaillé en équipe.",
      it: "Racconta una situazione in cui hai lavorato in squadra.",
      gsw: "Verzell vo ere Situation, wo du im Team gschaffet hesch.",
    },
  },
  {
    phase: "candidate_questions",
    text: {
      de: "Hast du noch Fragen an uns?",
      fr: "As-tu encore des questions pour nous ?",
      it: "Hai ancora delle domande per noi?",
      gsw: "Hesch du no Frage a üs?",
    },
  },
];

const closingMessage: Record<LanguageCode, string> = {
  de: "Vielen Dank{name}! Wir melden uns bald bei dir.",
  fr: "Merci beaucoup{name} ! Nous te recontacterons bientôt.",
  it: "Grazie mille{name}! Ti faremo sapere presto.",
  gsw: "Merci vielmal{name}! Mir melded üs bald bi dir.",
};

const tips: Record<LanguageCode, string> = {
  de: "Gute Antwort! Versuch noch ein konkretes Beispiel zu nennen.",
  fr: "Bonne réponse ! Essaie d'ajouter un exemple concret.",
  it: "Bella risposta! Prova ad aggiungere un esempio concreto.",
  gsw: "Guet gseit! Probier no es konkrets Bispiil z nenne.",
};

// Fixed report content (the real report is written by the LLM in the interview language)
const reportScores: { id: CriterionId; score: number }[] = [
  { id: "relevance", score: 4 },
  { id: "structure", score: 3 },
  { id: "examples", score: 4 },
  { id: "motivation", score: 4 },
  { id: "language", score: 5 },
  { id: "self_reflection", score: 2 },
];

const reportTexts: Record<
  LanguageCode,
  {
    labels: Record<CriterionId, string>;
    comments: Record<CriterionId, string>;
    strengths: string[];
    tip: string;
    exampleAnswer: string;
  }
> = {
  de: {
    labels: {
      relevance: "Relevanz",
      structure: "Struktur",
      examples: "Konkrete Beispiele",
      motivation: "Motivation",
      language: "Sprache & Ausdruck",
      self_reflection: "Selbstreflexion",
    },
    comments: {
      relevance: "Du bist meistens direkt auf die Frage eingegangen.",
      structure: "Gib deinen Antworten einen klaren Anfang und Schluss.",
      examples: "Dein Beispiel aus der Freizeit war anschaulich.",
      motivation: "Man spürt dein Interesse am Beruf.",
      language: "Freundlich und höflich formuliert.",
      self_reflection: "Überleg dir vorher, woran du noch arbeiten möchtest.",
    },
    strengths: ["Sympathischer Einstieg", "Echtes Interesse am Beruf"],
    tip: "Bereite eine Antwort auf 'Warum unsere Firma?' vor.",
    exampleAnswer: "Mich spricht an, dass Sie Lernende früh in echte Projekte einbinden ...",
  },
  fr: {
    labels: {
      relevance: "Pertinence",
      structure: "Structure",
      examples: "Exemples concrets",
      motivation: "Motivation",
      language: "Langue & expression",
      self_reflection: "Autoréflexion",
    },
    comments: {
      relevance: "Tu as le plus souvent répondu directement à la question.",
      structure: "Donne à tes réponses un début et une fin clairs.",
      examples: "Ton exemple tiré de tes loisirs était parlant.",
      motivation: "On sent ton intérêt pour le métier.",
      language: "Formulé de façon aimable et polie.",
      self_reflection: "Réfléchis à l'avance à ce que tu aimerais encore améliorer.",
    },
    strengths: ["Début sympathique", "Vrai intérêt pour le métier"],
    tip: "Prépare une réponse à « Pourquoi notre entreprise ? ».",
    exampleAnswer: "Ce qui me plaît, c'est que vous intégrez très tôt les apprentis à de vrais projets ...",
  },
  it: {
    labels: {
      relevance: "Pertinenza",
      structure: "Struttura",
      examples: "Esempi concreti",
      motivation: "Motivazione",
      language: "Lingua ed espressione",
      self_reflection: "Autoriflessione",
    },
    comments: {
      relevance: "Per lo più hai risposto direttamente alla domanda.",
      structure: "Dai alle tue risposte un inizio e una fine chiari.",
      examples: "Il tuo esempio del tempo libero era molto chiaro.",
      motivation: "Si sente il tuo interesse per la professione.",
      language: "Formulato in modo gentile e cortese.",
      self_reflection: "Pensa prima a cosa vorresti ancora migliorare.",
    },
    strengths: ["Inizio simpatico", "Vero interesse per la professione"],
    tip: "Prepara una risposta a «Perché la nostra azienda?».",
    exampleAnswer: "Mi piace che coinvolgiate gli apprendisti presto in progetti reali ...",
  },
  gsw: {
    labels: {
      relevance: "Relevanz",
      structure: "Struktur",
      examples: "Konkreti Bispiil",
      motivation: "Motivation",
      language: "Sprach & Uusdruck",
      self_reflection: "Selbstreflexion",
    },
    comments: {
      relevance: "Du bisch meischtens grad uf d Frog iigange.",
      structure: "Gib dine Antworte en klare Aafang und Schluss.",
      examples: "Dis Bispiil us de Freizit isch aaschaulich gsi.",
      motivation: "Mer spürt dis Interässe am Bruef.",
      language: "Fründlich und höflich formuliert.",
      self_reflection: "Überleg dir vorhär, a was d no wötsch schaffe.",
    },
    strengths: ["Sympathische Iistieg", "Ächts Interässe am Bruef"],
    tip: "Bereite e Antwort uf 'Wieso üsi Firma?' vor.",
    exampleAnswer: "Mi spricht a, dass Dir Lehrlig früeh i ächti Projäkt iibindet ...",
  },
};

type MockSession = {
  request: CreateSessionRequest;
  step: number; // index into `script` of the current question
  done: boolean;
  history: HistoryEntry[];
};

const sessions = new Map<string, MockSession>();

// ---------- helpers ----------

/** Wait 600-1200 ms so loading indicators are visible. */
function fakeDelay() {
  return new Promise((resolve) => setTimeout(resolve, 600 + Math.random() * 600));
}

function randomScore() {
  return 3 + Math.floor(Math.random() * 3); // 3, 4 or 5
}

function fill(text: string, session: MockSession) {
  const name = session.request.candidate?.first_name?.trim();
  return text.replace("{name}", name ? ` ${name}` : "");
}

function questionAt(session: MockSession, step: number) {
  return {
    id: `q${step + 1}`,
    text: fill(script[step].text[session.request.language], session),
    is_follow_up: false,
  };
}

function progress(step: number) {
  return { current: Math.min(step + 1, script.length), total: script.length };
}

function getOrThrow(sessionId: string) {
  const session = sessions.get(sessionId);
  if (!session) throw new ApiError("SESSION_NOT_FOUND", "No session with this id.");
  return session;
}

// ---------- the mock API ----------

export const mockApi: InterviewApi = {
  async getConfig() {
    await fakeDelay();
    return config;
  },

  async createSession(req) {
    await fakeDelay();
    if (!req.language || !req.occupation_id) {
      throw new ApiError("INVALID_REQUEST", "language and occupation_id are required.");
    }
    const session: MockSession = { request: req, step: 0, done: false, history: [] };
    const sessionId = crypto.randomUUID();
    sessions.set(sessionId, session);

    const question = questionAt(session, 0);
    session.history.push({ role: "interviewer", question_id: question.id, text: question.text });

    return { session_id: sessionId, phase: script[0].phase, progress: progress(0), question };
  },

  async sendAnswer(sessionId, questionId, text): Promise<AnswerResponse> {
    await fakeDelay();
    const session = getOrThrow(sessionId);
    if (session.done) throw new ApiError("INTERVIEW_FINISHED", "The interview is already over.");
    if (questionId !== `q${session.step + 1}`) {
      throw new ApiError("WRONG_QUESTION", "This is not the current question.");
    }

    session.history.push({ role: "candidate", question_id: questionId, text });

    const scores: Scores = {
      relevance: randomScore(),
      structure: randomScore(),
      examples: randomScore(),
      motivation: randomScore(),
      language: randomScore(),
      self_reflection: randomScore(),
    };
    const turnFeedback =
      session.request.mode === "training"
        ? { short_tip: tips[session.request.language], scores }
        : null;

    session.step += 1;

    // Last question answered -> interview is over
    if (session.step >= script.length) {
      session.done = true;
      return {
        done: true,
        phase: "closing",
        progress: progress(script.length - 1),
        question: null,
        closing_message: fill(closingMessage[session.request.language], session),
        turn_feedback: turnFeedback,
        meta: { llm_calls: 0, latency_ms: 0 },
      };
    }

    const question = questionAt(session, session.step);
    session.history.push({ role: "interviewer", question_id: question.id, text: question.text });
    return {
      done: false,
      phase: script[session.step].phase,
      progress: progress(session.step),
      question,
      turn_feedback: turnFeedback,
      meta: { llm_calls: 0, latency_ms: 0 },
    };
  },

  async getSession(sessionId): Promise<SessionState> {
    await fakeDelay();
    const session = getOrThrow(sessionId);
    return {
      session_id: sessionId,
      language: session.request.language,
      occupation_id: session.request.occupation_id,
      mode: session.request.mode,
      done: session.done,
      phase: session.done ? "closing" : script[session.step].phase,
      progress: progress(session.step),
      history: session.history,
      current_question_id: session.done ? null : `q${session.step + 1}`,
    };
  },

  async getReport(sessionId): Promise<Report> {
    await fakeDelay();
    const session = getOrThrow(sessionId);
    if (!session.done) {
      throw new ApiError("INTERVIEW_NOT_FINISHED", "The interview is not finished yet.");
    }
    const language = session.request.language;
    const r = reportTexts[language];
    const criteria = reportScores.map(({ id, score }) => ({
      id,
      label: r.labels[id],
      score,
      comment: r.comments[id],
    }));
    const average = criteria.reduce((sum, c) => sum + c.score, 0) / criteria.length;
    return {
      session_id: sessionId,
      language,
      overall_score: Math.round(average * 10) / 10,
      criteria,
      strengths: r.strengths,
      improvements: [{ tip: r.tip, example_answer: r.exampleAnswer }],
      next_practice: ["structure", "motivation"],
    };
  },

  // Accounts: the mock has no real accounts, any login works and nothing is saved
  async register(username): Promise<AuthResponse> {
    await fakeDelay();
    return { token: "mock-token", user: { id: "mock-user", username } };
  },

  async login(username): Promise<AuthResponse> {
    await fakeDelay();
    return { token: "mock-token", user: { id: "mock-user", username } };
  },

  async logout() {},

  async me(): Promise<User> {
    return { id: "mock-user", username: "mock" };
  },

  async listInterviews() {
    return [];
  },

  async getSavedInterview() {
    throw new ApiError("INTERVIEW_NOT_FOUND", "The mock does not save interviews.");
  },
};
