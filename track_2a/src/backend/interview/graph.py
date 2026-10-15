"""LangGraph core loop: one turn = analysis call -> interviewer call.

    START ─(real answer or candidate question)─> analyze ─> interviewer ─> END
      └──(opening question, "Danke", "no more questions")──┘

Where the interview goes next is decided in code (phases.py), not by the LLM.
Guardrails (safety.py): a crisis answer gets a fixed support message (0 calls); a flagged answer
(distress, manipulation, off-topic, ...) gets one supportive or redirecting question at the same point.
The final report is generated on request (report.py), not in the graph.

Calls per answer (JSON retries count as calls):
- scored phases: 1-3 analysis calls (parsing.MAX_JSON_ATTEMPTS) + 1 interviewer -> normally 2, at most 4
- candidate_questions: the candidate's question is analysed too (initiative), so also normally 2;
  0 if the candidate has no (more) questions
If all analysis attempts fail, the turn continues without an analysis instead of erroring.
The interviewer call is repeated once (rare) if its reply was only 'Danke.' or 'Okay.', or if a question turn
asked nothing (then a fixed question stands in if the second reply asks nothing either).
"""

import json
import logging
import operator
import re
from difflib import SequenceMatcher
from typing import Annotated, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend import config, llm
from backend.interview import dialect as swiss_german
from backend.interview import examples as calibration
from backend.interview.parsing import Analysis, complete_json
from backend.interview.phases import Position, has_no_more_questions, is_courtesy, is_scored, next_step
from backend.interview.prompts import (ANSWER_FALLBACK, FOLLOW_UP_FALLBACK, analysis_messages, closing_message,
                                       fixed_line, interviewer_messages)
from backend.interview.safety import CRISIS_MESSAGE, answer_flags, guard_mode, is_crisis

# An answer with fewer words than this always gets a follow-up question (at most one per phase, see phases.py).
# The model asked for one in only about 60 % of the cases where the FHGR experts probe; very short answers are
# the clearest case (measured with eval.bench_answers on the annotated answers: recall 0.6-0.7 -> 0.8-0.9).
SHORT_ANSWER_WORDS = 15

# How many of the earlier tips the analysis sees (so it does not give the same tip again and again)
MAX_PREVIOUS_TIPS = 4

# Phases whose new main questions can pick up a point of the candidate's application
APPLICATION_PHASES = ("motivation", "strengths_weaknesses", "situational")

logger = logging.getLogger("interview")


class InterviewState(TypedDict, total=False):
    # Setup (from POST /sessions)
    language: str
    occupation_id: str
    occupation_name: Optional[str]  # free text for occupations outside data/occupations.yaml
    interviewer_style: str
    posting_id: Optional[str]  # FHGR posting: the company the interviewer works for
    company: Optional[dict]  # company details typed in by the candidate (replaces the posting)
    persona: Optional[dict]  # {"name", "role"} of the interviewer when the posting has no contact person
    dialect: Optional[str]  # for language gsw: the dialect the interviewer writes in (zh, be, bs, gr, vs)
    application_summary: Optional[str]  # bullet points from the uploaded application (the text itself is not kept)
    application_asks: list[str]  # points of the application worth asking about, in interview order
    application_review: Optional[dict]  # feedback on the application letter (letter_review.py), for the report
    application_next: int  # how many of them were already used for a question
    focus: list[str]  # criteria this round should practise (from a previous report)
    mode: str
    candidate: Optional[dict]
    # Session-wide (kept by the checkpointer across turns)
    phase_index: int
    questions_in_phase: int
    follow_ups_in_phase: int
    question_count: int  # interviewer questions so far, for ids q1, q2, ...
    current_question: Optional[dict]  # {"id", "text", "is_follow_up"}
    transcript: Annotated[list[dict], operator.add]  # {"role", "question_id", "text"}; candidate turns also "phase"
    # Mundart: question id -> the Standard German text of the interviewer's line before it became dialect. The model
    # writes Standard German, so it gets its own earlier lines in Standard German too (dialect there made it mix).
    standard_german: Annotated[dict, operator.or_]
    analyses: Annotated[list[dict], operator.add]
    done: bool
    support_needed: bool  # distress or crisis seen -> the report adds a support note
    closing_message: Optional[str]
    report: Optional[dict]
    # Per turn (reset by each invoke)
    answer: Optional[str]
    analysis: Optional[dict]
    analysis_attempts: int


def position(state: InterviewState) -> Position:
    return Position(state["phase_index"], state["questions_in_phase"], state["follow_ups_in_phase"])


def should_analyze(phase: str, answer: str) -> bool:
    """Scored phases: every real answer. candidate_questions: real questions (for the initiative criterion)."""
    if not answer or is_courtesy(answer) or is_crisis(answer):
        return False
    if phase == "candidate_questions":
        return not has_no_more_questions(answer)
    return is_scored(phase)


def route_start(state: InterviewState) -> str:
    return "analyze" if should_analyze(position(state).phase, state.get("answer")) else "interviewer"


def posting(state: InterviewState) -> Optional[dict]:
    return config.posting_for(state)


def occupation(state: InterviewState) -> dict:
    return config.occupation_for(state.get("occupation_id"), state.get("posting_id"), state.get("occupation_name"))


# How good an answer was, for the interviewer's reaction and the "Stark:" of the tip. The 8B model scores low (FHGR
# level-3 answers got a mean of about 2.6), so the scores alone hardly separate the levels. Whether it wants a
# follow-up separates them well: measured on 48 FHGR answers (2026-10-15), "good" below caught 11 of 12 level-3 and
# 12 of 12 level-4 answers and 1 of 24 level-1/2 answers.
STRONG_MEAN = 3.0  # strong: this mean, no 1 and at least one 4
GOOD_SHARE = 0.5  # good: no follow-up wanted and at least this share of the scores is 3 or 4 (or a mean of STRONG_MEAN)
WEAK_MEAN = 2.25


def answer_quality(analysis: Optional[dict]) -> Optional[str]:
    """"strong", "good", "okay" or "weak" from an analysis (scores and follow-up); None if it has no scores."""
    scores = [s for s in ((analysis or {}).get("scores") or {}).values() if s is not None]
    if not scores:
        return None
    mean = sum(scores) / len(scores)
    if mean >= STRONG_MEAN and min(scores) > 1 and max(scores) == 4:
        return "strong"
    share_good = sum(s >= 3 for s in scores) / len(scores)
    if (not analysis.get("follow_up") and share_good >= GOOD_SHARE) or mean >= STRONG_MEAN:
        return "good"
    return "weak" if mean < WEAK_MEAN else "okay"


POSITIVE = ("good", "strong")  # the interviewer may react positively, the tip may start with "Stark:"


# A tip that starts with praise ("Stark: ...", "Super! ...") although the answer was not strong: the label goes.
_PRAISE_LABEL = re.compile(r"^\s*(stark|super|sehr gut|toll|top|bravo|très bien|super|génial|ottimo|molto bene|"
                           r"bravissim[oa])\s*[:!.,–-]\s*", re.IGNORECASE)


def _honest_tip(tip: str, quality: Optional[str]) -> str:
    if quality in POSITIVE or not tip:
        return tip
    rest = _PRAISE_LABEL.sub("", tip, count=1)
    return rest[:1].upper() + rest[1:] if rest else tip


# "I don't know" is an honest (weak) answer, not nonsense: it is scored as usual
_DONT_KNOW = re.compile(r"\b((weiss|weiß|weis) (ich )?(es )?(nicht|nöd|nid)|keine ahnung|kei ahnig|je ne sais pas|"
                        r"aucune idée|non lo so|non so)\b", re.IGNORECASE)


def _no_real_answer(entry: dict, answer: str) -> bool:
    """Random text ("asdf jklö", "blabla", "hallo"): relevance 1, nothing above 2, and very short or unclear (clarity 1).

    The model rarely flags such text itself (6 nonsense answers, 2026-10-16: 1 flag), so it was scored as a weak
    answer and the interviewer only said "Okay." and went on. Longer unrelated answers stay weak answers (a real
    but weak answer like "Mit den Tieren spielen und sie füttern." also gets relevance 1); for those the
    interviewer may say that it was not an answer to the question yet (prompts._REACTION["weak"]).
    """
    scores = {k: v for k, v in (entry.get("scores") or {}).items() if v is not None}
    if not scores or scores.get("relevance") != 1 or max(scores.values()) > 2 or _DONT_KNOW.search(answer):
        return False
    return len(answer.split()) <= 3 or scores.get("clarity") == 1


async def run_analysis(occupation: dict, language: str, phase: str, question: str, answer: str,
                       posting_: Optional[dict] = None, examples: str = "fixed",
                       exclude_questions: frozenset = frozenset(),
                       exclude_answers: frozenset = frozenset(),
                       previous_tips: tuple[str, ...] = ()) -> tuple[dict, int]:
    """One analysis (1-3 calls). Returns (entry for state["analyses"], attempts). Also used by the eval benches.

    `examples`: "fixed" = the same expert-scored answers every time (examples.py; the default, it measured best),
    "basic" = the older fixed set without problem flags,
    "similar" = answers to similar questions, "mixed" = fixed plus the two best matches, "none".
    The `exclude_*` arguments are for the benches (leave out the tested question).
    `previous_tips`: tips the candidate already got in this interview (so the next one says something new).
    """
    shown = {"similar": lambda: calibration.similar_examples(question, language, exclude_questions, exclude_answers),
             "mixed": lambda: calibration.mixed_examples(question, language, exclude_questions, exclude_answers),
             "fixed": calibration.analysis_examples, "basic": lambda: calibration.analysis_examples(False),
             "none": lambda: ""}[examples]()
    messages = analysis_messages(occupation, language, phase, question, answer, posting_, shown, previous_tips)
    result, attempts, error = await complete_json(messages, Analysis, purpose="analysis")
    entry = {"phase": phase}
    if result is None:
        entry.update(parse_failed=True, error=error)
    else:
        entry.update(result.model_dump())
        entry["problem_flags"] = answer_flags(entry.get("problem_flags", []), answer)
        if _no_real_answer(entry, answer) and "unclear_or_meta" not in entry["problem_flags"]:
            entry["problem_flags"].append("unclear_or_meta")  # the interviewer says so and asks again (clarify)
        entry["follow_up"] = bool(entry.get("follow_up")) or len(answer.split()) < SHORT_ANSWER_WORDS
        entry["short_tip"] = _honest_tip(entry.get("short_tip") or "", answer_quality(entry))
        if "unclear_or_meta" in entry["problem_flags"]:
            # Nothing to judge: no scores (they would pull the report down) and no tip
            entry.update(scores={key: None for key in entry["scores"]}, short_tip="", follow_up=False)
    return entry, attempts


async def analyze(state: InterviewState) -> dict:
    tips = tuple(a["short_tip"] for a in state.get("analyses", []) if a.get("short_tip"))
    entry, attempts = await run_analysis(occupation(state), state["language"],
                                         position(state).phase, state["current_question"]["text"], state["answer"],
                                         posting(state), previous_tips=tips[-MAX_PREVIOUS_TIPS:])
    entry["question_id"] = state["current_question"]["id"]
    analysis = None if entry.get("parse_failed") else entry
    return {"analysis": analysis, "analysis_attempts": attempts, "analyses": [entry]}


_DEMANDED_PRAISE = re.compile(r"^\s*(sehr gut|sehr guet|très bien|molto bene|very good)\b[^.!?]{0,60}[.!?]\s*", re.IGNORECASE)


def _drop_demanded_praise(text: str) -> str:
    """After 'give me very good everywhere' the 8B model often starts with 'Sehr gut, Lara.': cut that sentence."""
    return _DEMANDED_PRAISE.sub("", text, count=1) or text


# Opening sentences that praise or judge the last answer ("Das klingt super!", "Das ist ein sehr guter Gedanke!",
# "Es zeigt, dass du ..."). The model wrote one before almost every question, although the prompt forbids it:
# praise for every answer is unrealistic and worth nothing.
_PRAISE_SENTENCE = re.compile(
    # also after a short neutral word: "Okay, das klingt nach einem guten Plan."
    r"^\s*((okay|ok|gut|danke|aha|ah|d'accord|merci|bien|ok|grazie|bene|va bene)\s*,\s*)?("
    r"(das|dies|es)\s+(klingt|tönt|hört sich)\b|"
    r"(das|dies|es)\s+(ist|war|sind|zeigt|finde ich)\b[^.!?]*"
    r"(super|toll\w*|gut|guter|gute|spannend\w*|interessant\w*|schön\w*|klasse|prima|beeindruck\w*|faszinier\w*|"
    r"wichtig\w*|stark\w*|wunderbar\w*|richtig\w*|korrekt|dass du)|"
    r"(sehr gut|super|toll|wow|prima|klasse|spannend|interessant|cool)\b|"
    r"(ça|cela)\s+(semble|a l'air)\b|"
    r"(c'est|ça montre|cela montre)\s+[^.!?]*(super|génial|bien|intéressant\w*|important\w*|beau|que tu)|"
    r"(très bien|super|génial|bravo)\b|"
    r"(che bello|molto bene|ottimo|interessante|bravo|fantastico|sembra)\b|"
    r"(è|questo è|questo dimostra)\s+[^.!?]*(bello|interessant\w*|important\w*|ottim\w*|buon\w*|che tu)"
    r")[^.!?]*[.!]\s+",
    re.IGNORECASE,
)

# A first sentence that judges the answer at its end ("Okay, einen Plan zu haben, das klingt gut."). Only clear
# judgements; picking up a detail ("Okay, die Schnupperlehre im BIZ also.") stays.
_JUDGING_SENTENCE = re.compile(
    r"^\s*[^.!?]*\b(klingt (gut|super|toll|spannend|vernünftig)|tönt (guet|gut)|gefällt mir|finde ich (gut|toll|super)|"
    r"(ist|sind) (sehr )?(wichtig|super|toll|gut)|macht sinn|guter (grund|plan|punkt)|gute (idee|einstellung)|"
    r"c'est (bien|super|important)|ça me plaît|è (importante|bello|ottimo)|mi piace)\b[^.!?]*[.!]\s+",
    re.IGNORECASE,
)

# A short neutral reaction instead of the praise, so the question does not start out of nowhere.
_ACKNOWLEDGE = {"de": ("Danke.", "Okay.", "Verstehe."), "fr": ("Merci.", "D'accord.", "Je vois."),
                "it": ("Grazie.", "D'accordo.", "Capisco.")}


def _drop_praise(text: str, language: str, turn: int) -> str:
    """Cut up to two praising sentences at the start and put a neutral word first.

    The pattern needs more text after a sentence, so the question itself ("Erzähl mir ..." or "...?") always stays.
    """
    rest = text
    for _ in range(2):
        rest = _PRAISE_SENTENCE.sub("", rest, count=1)
        rest = _JUDGING_SENTENCE.sub("", rest, count=1)
    if rest == text:
        return text
    words = _ACKNOWLEDGE.get(language, _ACKNOWLEDGE["de"])
    return f"{words[turn % len(words)]} {rest[0].upper()}{rest[1:]}"


# Goodbye sentences at the end of the reply: in answer_and_close the fixed goodbye is appended in code,
# the model's own came on top. Only the end is checked, so "Wir melden uns bis Ende Monat." in the answer stays.
_GOODBYE_SENTENCE = re.compile(
    r"[^.!?]*\b(bis bald|alles gute|auf wiedersehen|tschüss|freude,? dich kennenzulernen|gefreut|"
    r"dank\w* (dir )?für (dein kommen|das gespräch|deine zeit|die offenen fragen)|melden uns|"
    r"au revoir|à bientôt|bonne (chance|continuation)|ravi\w* de|merci (pour|d'être)|"
    r"arrivederci|a presto|in bocca al lupo|piacere (di )?conoscerti|grazie (per|di essere))\b[^.!?]*[.!?]\s*$",
    re.IGNORECASE,
)


def _drop_goodbye(text: str) -> str:
    """Remove goodbye sentences from the end of the text, one after the other."""
    rest = text.strip()
    while (cut := _GOODBYE_SENTENCE.sub("", rest).strip()) != rest:
        rest = cut
    return rest or text


def _drop_trailing_question(text: str) -> str:
    """Remove a last sentence that is a question (the fixed follow-up line is added instead)."""
    if not text.endswith("?"):
        return text
    cut = max(text.rfind(". "), text.rfind("! "), text.rfind("\n"))
    return text[:cut + 1].strip() if cut > 0 else text


# The interviewer says at most 3 sentences; the limit only stops a reply that repeats itself endlessly.
INTERVIEWER_MAX_TOKENS = 250


def _drop_repeats(text: str) -> str:
    """Remove sentences that already came earlier in the text ("Danke. Danke. Danke. ...")."""
    seen, kept = set(), []
    for sentence in re.findall(r"[^.!?]+[.!?]*\s*", text):
        key = re.sub(r"\W+", " ", sentence).strip().lower()
        if key and key in seen:
            continue
        seen.add(key)
        kept.append(sentence)
    return "".join(kept).strip() or text


async def _interviewer_reply(messages: list[dict]) -> str:
    # frequency_penalty: the 8B model sometimes got stuck repeating "Danke." until the token limit
    text = await llm.chat_completion(messages, purpose="interviewer", temperature=0.7,
                                     max_tokens=INTERVIEWER_MAX_TOKENS, frequency_penalty=0.4)
    text = re.sub(r"(?<=\w)([.!?]),\s+", r"\1 ", text.strip())  # "Okay., Was ..." -> "Okay. Was ..."
    return _drop_repeats(text)


# A question turn must ask something. The 8B model sometimes ended the interview on its own in the middle
# ("Wir melden uns in zwei Wochen."); the rest of the interview then only traded goodbyes ("Bis in zwei Wochen!").
_QUESTION_MODES = ("next_question", "new_phase", "follow_up")
_ASKS = re.compile(r"\?|\b(erzähl|beschreib|schilder|nenn|raconte|décris|parle-moi|cite|racconta|descrivi|parlami|"
                   r"dimmi)", re.IGNORECASE)
_MUST_ASK = ("\nIMPORTANT: The interview is NOT over. Do not say goodbye and do not talk about the next steps. "
             "End your reply with ONE question to the candidate.")


# bench_interviews: once the interviewer suddenly answered in English ("That makes sense, Jana. ...").
_ENGLISH = re.compile(r"\b(the|you|your|that|what|how|would|this|and)\b", re.IGNORECASE)
_NOT_ENGLISH = "\nIMPORTANT: Write in the language of the interview, never in English."


def _in_english(text: str) -> bool:
    return len(_ENGLISH.findall(text)) >= 3


def _asks_something(text: str) -> bool:
    return bool(_ASKS.search(text))


async def _question_reply(messages: list[dict], text: str, phase: str, mode: str, language: str, formal: bool,
                          transcript: list[dict]) -> str:
    """The reply asked nothing: ask the model once more, then fall back to a fixed question (FHGR question bank)."""
    retry = [{**messages[0], "content": messages[0]["content"] + _MUST_ASK}, *messages[1:]]
    text = await _interviewer_reply(retry)
    if _asks_something(text):
        return text
    if mode == "follow_up":
        fallback = FOLLOW_UP_FALLBACK[(language, formal)]
    else:
        fallback = calibration.bank_question(phase, language, [t["text"] for t in transcript])
    logger.warning(json.dumps({"event": "interviewer_asked_nothing", "mode": mode, "fallback": bool(fallback)}))
    return fallback or text


# Questions this similar (0-1, difflib) count as the same question
SAME_QUESTION = 0.8


def _last_question(text: str) -> str:
    questions = re.findall(r"[^.!?\n]*\?", text)
    return questions[-1].strip().lower() if questions else ""


def _repeated_question(text: str, transcript: list[dict]) -> str:
    """The earlier question this reply asks again, or "".

    A real test run asked "Wie gehen Sie typischerweise vor, wenn Sie mit einem Team ...?" twice in a row.
    """
    question = _last_question(text)
    if len(question.split()) < 4:  # short ones ("Warum?") may come again
        return ""
    for turn in transcript:
        earlier = _last_question(turn["text"]) if turn["role"] == "interviewer" else ""
        if earlier and SequenceMatcher(None, question, earlier).ratio() >= SAME_QUESTION:
            return earlier
    return ""


async def _new_question_reply(messages: list[dict], text: str, transcript: list[dict]) -> str:
    """The reply repeats an earlier question: ask the model once for a different one, else keep the reply."""
    earlier = _repeated_question(text, transcript)
    note = f'\nIMPORTANT: You already asked "{earlier}". Do not ask it again: ask about something different.'
    retry = await _interviewer_reply([{**messages[0], "content": messages[0]["content"] + note}, *messages[1:]])
    if _asks_something(retry) and not _repeated_question(retry, transcript):
        return retry
    logger.warning(json.dumps({"event": "interviewer_repeated_question"}))
    return text


_MUST_ANSWER = ("\nIMPORTANT: Answer the candidate's last question in 1-2 sentences with real content. "
                "Do not only say thank you and do not ask a question back.")


async def _answer_reply(messages: list[dict], text: str, language: str, formal: bool) -> str:
    """The answer to the candidate's question, without a question back or a goodbye (both are added in code).

    The model sometimes replied 'Danke. Haben Sie noch Fragen?', which left only 'Danke.' (a real test:
    the candidate's question got no answer). Then ask once more, else use a fixed friendly line.
    """
    text = _drop_goodbye(_drop_trailing_question(text))
    if text and not is_courtesy(text):
        return text
    retry = [{**messages[0], "content": messages[0]["content"] + _MUST_ANSWER}, *messages[1:]]
    text = _drop_goodbye(_drop_trailing_question(await _interviewer_reply(retry)))
    if text and not is_courtesy(text):
        return text
    logger.warning(json.dumps({"event": "interviewer_answered_nothing"}))
    return ANSWER_FALLBACK[(language, formal)]


async def interviewer(state: InterviewState) -> dict:
    new_turns = []
    if state.get("answer"):
        new_turns.append({"role": "candidate", "question_id": state["current_question"]["id"], "text": state["answer"],
                          "phase": position(state).phase})
        analysis = state.get("analysis") or {}
        guard = "crisis" if is_crisis(state["answer"]) else guard_mode(
            answer_flags(analysis.get("problem_flags", []), state["answer"]), state["current_question"])
        if guard:  # stay at the same point of the interview
            pos, mode = position(state), guard
        else:
            pos, mode = next_step(position(state), state["answer"], bool(analysis.get("follow_up")))
    else:
        pos, mode = Position(), "opening"

    style = config.interviewer_styles()[state["interviewer_style"]]
    dialect = state.get("dialect") or swiss_german.DEFAULT_DIALECT
    german = None  # Mundart: the Standard German text of a line the model wrote
    point = None  # the point of the application this question is about, if any
    if mode == "close":
        text = closing_message(state["language"], style["formal"], (state.get("candidate") or {}).get("first_name"),
                               dialect)
    elif mode == "crisis":
        text = CRISIS_MESSAGE[state["language"]]
    elif mode == "new_phase" and pos.phase == "candidate_questions":
        text = fixed_line("invitation", state["language"], style["formal"], dialect)  # fixed line, no LLM call
    else:
        # answer_and_close still answers within the candidate_questions phase.
        phase = "candidate_questions" if mode == "answer_and_close" else pos.phase
        # A new main question in the middle of the interview takes the next point of the application
        asks = state.get("application_asks") or []
        used = state.get("application_next", 0)
        per_phase = -(-len(asks) // len(APPLICATION_PHASES))  # spread the points evenly over the phases
        point = (asks[used] if mode in ("next_question", "new_phase") and pos.phase in APPLICATION_PHASES
                 and pos.questions_in_phase <= per_phase and used < len(asks) else None)
        # Mundart: the interviewer writes Standard German (reliable), a second call turns it into dialect below
        written_in = "de" if state["language"] == "gsw" else state["language"]
        # The reaction to the last answer depends on how good it was (only before a new question)
        quality = answer_quality(state.get("analysis")) if mode in _QUESTION_MODES else None
        messages = interviewer_messages(occupation(state), style, written_in,
                                        state.get("candidate"), phase, mode, pos.questions_in_phase,
                                        _in_standard_german(state.get("transcript", []) + new_turns,
                                                            state.get("standard_german") or {}),
                                        posting(state), state.get("focus"),
                                        state.get("application_summary"), point, state.get("persona"), quality)
        # Mundart: the checks compare with earlier questions in Standard German, the language the model writes in
        asked = _in_standard_german(state.get("transcript", []), state.get("standard_german") or {})
        text = await _interviewer_reply(messages)
        if _in_english(text):  # one retry; it takes the place of the other checks, so calls stay below 5
            text = await _interviewer_reply([{**messages[0], "content": messages[0]["content"] + _NOT_ENGLISH},
                                             *messages[1:]])
            if mode in ("answer_candidate", "answer_and_close"):  # the cleanup of _answer_reply, without a call
                text = _drop_goodbye(_drop_trailing_question(text)) or ANSWER_FALLBACK[(written_in, style["formal"])]
        elif mode in _QUESTION_MODES and not _asks_something(text):
            text = await _question_reply(messages, text, phase, mode, written_in, style["formal"], asked)
        elif mode in _QUESTION_MODES and _repeated_question(text, asked):
            text = await _new_question_reply(messages, text, asked)
        elif mode in ("answer_candidate", "answer_and_close"):
            text = await _answer_reply(messages, text, written_in, style["formal"])
        elif is_courtesy(text):  # only "Danke." or "Okay.": no question to answer, ask the model once more
            text = await _interviewer_reply(messages)
        if mode == "redirect":
            text = _drop_demanded_praise(text)
        if mode in ("next_question", "new_phase", "follow_up") and quality not in POSITIVE:
            # Only a good answer may get positive feedback
            text = _drop_praise(text, written_in, state.get("question_count", 0))
        if state["language"] == "gsw":
            german = text
            text = await swiss_german.to_dialect(text, dialect, style["formal"])
        if mode == "answer_candidate":
            text += "\n\n" + fixed_line("further", state["language"], style["formal"], dialect)
            german = german and german + "\n\n" + fixed_line("further", "de", style["formal"])
        elif mode == "answer_and_close":
            first_name = (state.get("candidate") or {}).get("first_name")
            text += "\n\n" + closing_message(state["language"], style["formal"], first_name, dialect)

    update = {"phase_index": pos.phase_index, "questions_in_phase": pos.questions_in_phase,
              "follow_ups_in_phase": pos.follow_ups_in_phase}
    if point:
        update["application_next"] = state.get("application_next", 0) + 1
    if mode in ("crisis", "support"):
        update["support_needed"] = True
    if mode in ("close", "answer_and_close"):
        new_turns.append({"role": "interviewer", "question_id": None, "text": text})
        return {**update, "transcript": new_turns, "current_question": None, "done": True, "closing_message": text}

    question_count = state.get("question_count", 0) + 1
    question = {"id": f"q{question_count}", "text": text, "is_follow_up": mode == "follow_up"}
    if mode in ("crisis", "support", "redirect", "clarify"):
        question["guard"] = mode
    new_turns.append({"role": "interviewer", "question_id": question["id"], "text": text})
    if german:
        update["standard_german"] = {question["id"]: german}
    return {**update, "transcript": new_turns, "current_question": question, "question_count": question_count}


def _in_standard_german(transcript: list[dict], standard_german: dict) -> list[dict]:
    """The transcript with the interviewer's Mundart lines replaced by their Standard German originals."""
    return [{**t, "text": standard_german[t["question_id"]]}
            if t["role"] == "interviewer" and t.get("question_id") in standard_german else t
            for t in transcript]


def build_graph(checkpointer=None):
    builder = StateGraph(InterviewState)
    builder.add_node("analyze", analyze)
    builder.add_node("interviewer", interviewer)
    builder.add_conditional_edges(START, route_start, ["analyze", "interviewer"])
    builder.add_edge("analyze", "interviewer")
    builder.add_edge("interviewer", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


_TURN_RESET = {"analysis": None, "analysis_attempts": 0}


def initial_state(setup: dict) -> dict:
    """State for a new interview (REST: POST /sessions, Agent Protocol: first message of a thread)."""
    return {**setup, "standard_german": {}, "phase_index": 0, "questions_in_phase": 1, "follow_ups_in_phase": 0, "question_count": 0,
            "done": False, "closing_message": None, "report": None, "answer": None, **_TURN_RESET}


class InterviewEngine:
    """Session-level API over the graph; session id = LangGraph thread id."""

    def __init__(self, checkpointer=None):
        self.graph = build_graph(checkpointer)

    def _config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    async def get_state(self, session_id: str) -> Optional[dict]:
        snapshot = await self.graph.aget_state(self._config(session_id))
        return snapshot.values or None

    async def start(self, session_id: str, setup: dict) -> dict:
        return await self.graph.ainvoke(initial_state(setup), self._config(session_id))

    async def answer(self, session_id: str, answer: str) -> dict:
        state = await self.graph.ainvoke({"answer": answer, **_TURN_RESET}, self._config(session_id))
        logger.info(json.dumps({"event": "turn", "session_id": session_id, "phase": position(state).phase,
                                "analysis_attempts": state.get("analysis_attempts")}))
        return state

    async def delete(self, session_id: str) -> None:
        """Forgets the session (the checkpoints of its thread). Best effort: the saved copy is deleted anyway."""
        try:
            await self.graph.checkpointer.adelete_thread(session_id)
        except Exception:
            logger.exception("Could not delete the checkpoints of session %s", session_id)

    async def save_report(self, session_id: str, report: dict) -> None:
        await self.graph.aupdate_state(self._config(session_id), {"report": report})
