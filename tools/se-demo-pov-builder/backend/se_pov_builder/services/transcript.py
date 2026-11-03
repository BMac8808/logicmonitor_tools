"""Turn a pasted call transcript or question list into *proposals* for the SE to review.

Nothing here touches the database: transcripts are processed in memory and discarded.
Only proposals the SE accepts are saved (as assumed answers, with the accepted quote).

* ``parse_transcript`` reads WebVTT, SRT or plain text ("Speaker: words", optional
  "[hh:mm:ss]" prefix) into segments.
* ``keyword_proposals`` matches segments to questions with the question's "listen for"
  phrases, its own key words and its related capabilities' keywords. No LLM involved.
* ``verify_ai_proposals`` keeps an AI proposal only if its quote appears word for word in
  the transcript.
* ``parse_question_list`` splits a pasted list into candidate custom questions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..knowledge import KnowledgeBase
from .questions import QuestionRef

STOPWORDS = set("""
a about above after again against all am an and any are as at be because been before being below between both but
by can could did do does doing down during each few for from further had has have having he her here hers him his
how i if in into is it its itself just me more most my no nor not now of off on once only or other our ours out over
own same she should so some such than that the their them then there these they this those through to too under
until up very was we were what when where which while who whom why will with would you your yours yourself
today currently typical typically usually across today's there's it's we're they're i'm you're let's tell much many
way thing things get got go going really kind sort also one two lot like well know think yeah yes okay ok um uh
last first next
""".split())
_WORD = re.compile(r"[a-z0-9][a-z0-9'%&+-]*")
_TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
_CUE_TIME = re.compile(rf"^\s*({_TS})\s*-->\s*({_TS})")
_NAME = r"[A-Z][\w.'’-]*(?:\s[A-Z][\w.'’-]*){0,3}"
_TEXT_LINE = re.compile(rf"^\s*(?:\[?({_TS})\]?\s*[-–]?\s*)?(?:({_NAME})\s*:\s+)?(.*)$")
_VOICE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
_TAG = re.compile(r"</?[^>]+>")
MAX_SEGMENT = 700
MAX_PAUSE_SECONDS = 5
# "How many / how long / what did it cost" questions are usually answered with a number.
_QUANTITY_QUESTION = re.compile(r"\bhow (?:many|much|long|often)\b|\bcost\b|\bwhat share\b", re.IGNORECASE)
_QUANTITY = re.compile(
    r"\d|\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|million|dozen|half)\b", re.IGNORECASE)
MAX_QUOTE = 600


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s", "ly"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def stems(text: str) -> set[str]:
    return {stem(w.strip("'")) for w in _WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 2}


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Segment:
    text: str
    speaker: str | None = None
    start: str | None = None
    # Cue times in seconds (captions only); used to decide which cues belong together.
    start_s: float | None = field(default=None, repr=False)
    end_s: float | None = field(default=None, repr=False)


def _seconds(ts: str) -> float:
    parts = [float(p) for p in ts.replace(",", ".").split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def _short_ts(ts: str | None) -> str | None:
    if not ts:
        return None
    ts = re.split(r"[.,]", ts)[0]
    return ts if ts.count(":") == 2 else f"00:{ts}" if ts.count(":") == 1 else ts


def _merge(segments: list[Segment]) -> list[Segment]:
    """Join consecutive cues from the same speaker (captions split sentences across cues)."""
    merged: list[Segment] = []
    for seg in segments:
        prev = merged[-1] if merged else None
        close = (prev is not None and (prev.end_s is None or seg.start_s is None
                                       or seg.start_s - prev.end_s <= MAX_PAUSE_SECONDS))
        if (prev and close and seg.speaker and prev.speaker == seg.speaker
                and len(prev.text) + len(seg.text) < MAX_SEGMENT):
            prev.text = f"{prev.text} {seg.text}"
            prev.end_s = seg.end_s
        else:
            merged.append(Segment(seg.text, seg.speaker, seg.start, seg.start_s, seg.end_s))
    return merged


def _cue_text(lines: list[str]) -> tuple[str | None, str]:
    speaker = None
    parts = []
    for line in lines:
        voice = _VOICE.search(line)
        if voice:
            speaker = voice.group(1).strip()
        parts.append(_TAG.sub("", line))
    text = normalise(" ".join(parts))
    if speaker is None:  # "Name: words" inside the cue text
        m = re.match(rf"^({_NAME})\s*:\s+(.*)$", text)
        if m:
            speaker, text = m.group(1), m.group(2)
    return speaker, text


def parse_transcript(text: str, filename: str = "") -> tuple[str, list[Segment]]:
    """Returns (format, segments). Format is "vtt", "srt" or "text"."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = text.split("\n")
    name = filename.lower()
    is_vtt = name.endswith(".vtt") or text.lstrip().startswith("WEBVTT")
    is_srt = not is_vtt and (name.endswith(".srt") or any(_CUE_TIME.match(line) for line in lines[:12]))

    if is_vtt or is_srt:
        segments: list[Segment] = []
        blocks = re.split(r"\n\s*\n", text)
        for block in blocks:
            block_lines = [ln for ln in block.split("\n") if ln.strip()]
            idx = next((i for i, ln in enumerate(block_lines) if _CUE_TIME.match(ln)), None)
            if idx is None:
                continue  # header, NOTE, STYLE or REGION block
            times = _CUE_TIME.match(block_lines[idx])
            if times is None:  # pragma: no cover - idx was found with the same pattern
                continue
            speaker, cue = _cue_text(block_lines[idx + 1:])
            if cue:
                segments.append(Segment(cue, speaker, _short_ts(times.group(1)),
                                        _seconds(times.group(1)), _seconds(times.group(2))))
        return ("vtt" if is_vtt else "srt"), _merge(segments)

    segments = []
    for line in lines:
        if not line.strip():
            continue
        m = _TEXT_LINE.match(line)
        ts, speaker, body = (m.group(1), m.group(2), m.group(3)) if m else (None, None, line)
        body = normalise(body)
        if body:
            segments.append(Segment(body, speaker, _short_ts(ts)))
    return "text", _merge(segments)


# --- Keyword proposals --------------------------------------------------------
@dataclass
class Proposal:
    question_id: str
    quote: str
    speaker: str | None
    timestamp: str | None
    proposed_answer: str
    matched: list[str]
    method: str
    score: int
    segment_index: int = 0


@dataclass
class _Terms:
    phrases: list[tuple[str, set[str]]]
    keywords: list[tuple[str, set[str]]]
    words: set[str] = field(default_factory=set)


# Words that appear in many questions and say little about the topic.
_GENERIC_QUESTION_WORDS = {stem(w) for w in """
team teams use used using need needs want wants happen happens part parts change changes work works
long time take takes""".split()}


def _terms(kb: KnowledgeBase, q: QuestionRef) -> _Terms:
    phrases = [(p, stems(p)) for p in q.listen_for]
    keywords = []
    for cap_id in q.suggests_capabilities:
        cap = kb.capabilities.get(cap_id)
        if cap:
            keywords += [(k, stems(k)) for k in cap.keywords]
    return _Terms(phrases=[p for p in phrases if p[1]], keywords=[k for k in keywords if k[1]],
                  words=stems(q.text) - _GENERIC_QUESTION_WORDS)


def _score(terms: _Terms, seg_stems: set[str]) -> tuple[int, list[str]]:
    score, matched = 0, []
    for phrase, ph in terms.phrases:
        if ph <= seg_stems:
            score += 3
            matched.append(phrase)
    kw_hits = [k for k, ks in terms.keywords if ks <= seg_stems and k not in matched]
    score += min(len(kw_hits), 2)
    matched += kw_hits[:2]
    overlap = sorted(terms.words & seg_stems)
    score += min(len(overlap), 3)
    matched += [w for w in overlap[:3] if not any(w in stems(m) for m in matched)]
    return score, matched


def _trim_quote(text: str, matched: list[str]) -> str:
    """Long segments: keep the sentences around the matches (still an exact substring)."""
    if len(text) <= MAX_QUOTE:
        return text
    sentences = [m for m in re.finditer(r"[^.!?]+[.!?]*", text) if m.group().strip()]
    wanted = set().union(*(stems(m) for m in matched)) if matched else set()
    hits = [i for i, s in enumerate(sentences) if stems(s.group()) & wanted]
    if not hits:
        return text[:MAX_QUOTE].rsplit(" ", 1)[0]
    first = hits[0]
    last = first
    while last + 1 < len(sentences) and sentences[last + 1].end() - sentences[first].start() <= MAX_QUOTE:
        last += 1
        if last >= hits[-1]:
            break
    return text[sentences[first].start():sentences[last].end()].strip()


def keyword_proposals(
    kb: KnowledgeBase, questions: Iterable[QuestionRef], segments: list[Segment], per_segment: int = 2,
) -> list[Proposal]:
    """Best matching segment per question. A segment that *asks* a question (ends with "?")
    is never the answer; the reply that follows it gets a bonus instead."""
    qlist = list(questions)
    terms = {q.id: _terms(kb, q) for q in qlist}
    seg_stems = [stems(s.text) for s in segments]
    best: dict[str, Proposal] = {}

    # A question the SE asks out loud boosts the reply that follows, for the one bank
    # question it matches best.
    asked: dict[tuple[str, int], int] = {}
    for i, seg in enumerate(segments):
        if not seg.text.rstrip().endswith("?"):
            continue
        scored = [(_score(terms[q.id], seg_stems[i])[0], q.id) for q in qlist]
        top_score, top_id = max(scored, default=(0, ""))
        if top_score < 3:
            continue
        nxt = next((j for j in range(i + 1, min(i + 3, len(segments)))
                    if not segments[j].text.rstrip().endswith("?")), None)
        if nxt is not None:
            asked[(top_id, nxt)] = 3

    for q in qlist:
        t = terms[q.id]
        wants_quantity = bool(_QUANTITY_QUESTION.search(q.text))
        for i, seg in enumerate(segments):
            if seg.text.rstrip().endswith("?") or len(seg_stems[i]) < 3:
                continue
            score, matched = _score(t, seg_stems[i])
            overlap = len(t.words & seg_stems[i])
            quantity = wants_quantity and bool(_QUANTITY.search(seg.text))
            if quantity:
                score += 1
            bonus = asked.get((q.id, i), 0)
            if bonus:
                score += bonus
                matched = [*matched, "reply to this question"]
            has_signal = (any(m in dict(t.phrases) for m in matched) or bonus or score >= 4
                          or (quantity and overlap >= 2))
            if score < 3 or not has_signal:
                continue
            if q.id not in best or score > best[q.id].score:
                quote = _trim_quote(seg.text, [m for m in matched if m != "reply to this question"])
                best[q.id] = Proposal(q.id, quote, seg.speaker, seg.start, quote, matched, "keyword", score, i)

    # A segment rarely answers more than a couple of questions: keep its strongest matches.
    by_segment: dict[int, list[Proposal]] = {}
    for p in best.values():
        by_segment.setdefault(p.segment_index, []).append(p)
    kept: list[Proposal] = []
    for props in by_segment.values():
        kept += sorted(props, key=lambda p: -p.score)[:per_segment]
    order = {q.id: n for n, q in enumerate(qlist)}
    return sorted(kept, key=lambda p: (p.segment_index, order[p.question_id]))


# --- Optional AI proposals ------------------------------------------------------
AI_SYSTEM = (
    "You read a sales discovery call transcript and find where the customer answered the listed "
    "questions. Reply with a JSON array only. Each item: {\"question_id\": one of the listed ids, "
    "\"quote\": the customer's exact words copied character for character from the transcript, "
    "\"answer\": a one-sentence answer using only what the quote says}. Skip questions that were "
    "not answered. Never paraphrase inside \"quote\" and never invent numbers."
)


def ai_prompt(questions: Iterable[QuestionRef], segments: list[Segment], max_chars: int = 24_000) -> str:
    lines = ["Questions:"] + [f"- {q.id}: {q.text}" for q in questions] + ["", "Transcript:"]
    used = 0
    for seg in segments:
        line = f"[{seg.start or '-'}] {seg.speaker or 'Unknown'}: {seg.text}"
        used += len(line)
        if used > max_chars:
            lines.append("[transcript truncated]")
            break
        lines.append(line)
    return "\n".join(lines)


def verify_ai_proposals(
    raw: str, questions: Mapping[str, QuestionRef], segments: list[Segment],
) -> tuple[list[Proposal], int]:
    """Parse the model's JSON. Keep items whose quote appears verbatim (ignoring case and
    whitespace) in one transcript segment. Returns (proposals, rejected count)."""
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("The AI response did not contain a JSON list")
    items = json.loads(raw[start:end + 1])
    if not isinstance(items, list):
        raise ValueError("The AI response was not a JSON list")
    norm_segments = [normalise(s.text).lower() for s in segments]
    kept: list[Proposal] = []
    rejected = 0
    for item in items:
        if not isinstance(item, dict):
            rejected += 1
            continue
        qid = str(item.get("question_id", ""))
        quote = normalise(str(item.get("quote", ""))).strip(" \"'“”‘’…")
        answer = normalise(str(item.get("answer", ""))) or quote
        idx = next((i for i, s in enumerate(norm_segments) if quote and quote.lower() in s), None)
        if qid not in questions or idx is None or len(quote) < 8:
            rejected += 1
            continue
        seg_text = normalise(segments[idx].text)
        pos = seg_text.lower().index(quote.lower())
        exact = seg_text[pos:pos + len(quote)]  # the transcript's own spelling and case
        kept.append(Proposal(qid, exact, segments[idx].speaker, segments[idx].start, answer[:2000],
                             [], "ai", 0, idx))
    return kept, rejected


# --- Question lists -----------------------------------------------------------
_BULLET = re.compile(r"^\s*(?:[-*•–]+|\(?\d+[.)]|Q\d*\s*[:.)-]|[a-z][.)])\s*", re.IGNORECASE)
_CATEGORY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("qualification", ("budget", "timeline", "criteria", "competitor", "evaluat", "procurement", "deadline",
                       "renewal", "alternative", "pricing", "cost")),
    ("stakeholder", ("who ", "decision", "sign off", "sign-off", "approv", "stakeholder", "involved", "champion")),
    ("process", ("process", "escalat", "incident", "on-call", "on call", "workflow", "ticket", "runbook",
                 "change management", "handoff", "triage")),
    ("technical", ("monitor", "network", "server", "cloud", "aws", "azure", "gcp", "kubernetes", "container",
                   "alert", "log", "device", "api", "integrat", "collector", "storage", "database", "vmware",
                   "firewall", "application", "metric", "tool", "branch", "site", "wan", "lan", "switch", "router",
                   "vpn", "wireless", "latency", "uptime", "outage", "dashboard")),
]


def guess_category(text: str) -> str:
    lowered = f" {text.lower()} "
    for category, hints in _CATEGORY_HINTS:
        if any(h in lowered for h in hints):
            return category
    return "business"


LIKELY_DUPLICATE = 0.6
# Natural rewordings of a bank question score about 0.10-0.43, and new questions on the same
# topics up to about 0.18, so a match between these thresholds is only a hint.
POSSIBLE_DUPLICATE = 0.25


def closest_question(text: str, questions: Iterable[QuestionRef]) -> tuple[QuestionRef | None, float]:
    """The most similar question by word overlap (Jaccard on stems), with its score."""
    mine = stems(text)
    if not mine:
        return None, 0.0
    best, best_score = None, 0.0
    for q in questions:
        theirs = stems(q.text)
        if not theirs:
            continue
        overlap = len(mine & theirs)
        score = overlap / len(mine | theirs)
        if overlap >= 3 and overlap / min(len(mine), len(theirs)) >= 0.8:
            score = max(score, LIKELY_DUPLICATE)  # one question is the other plus some detail
        if score > best_score:
            best, best_score = q, score
    return best, best_score


def parse_question_list(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in text.replace("\r", "\n").split("\n"):
        line = normalise(_BULLET.sub("", line))
        if len(line.split()) < 3 or len(line) > 500:
            continue
        if line.endswith(":") and "?" not in line:
            continue  # a heading
        key = line.lower().rstrip("?. ")
        if key not in seen:
            seen.add(key)
            out.append(line)
    return out


def proposal_receipt(key: bytes, deal_id: int, question_id: str, quote: str, speaker: str | None,
                     timestamp: str | None, filename: str) -> str:
    """HMAC over what a saved answer will claim about its source, so accept only takes quotes this
    server found in a transcript. The answer text is not covered: the SE may edit it."""
    message = json.dumps([deal_id, question_id, quote, speaker or "", timestamp or "", filename])
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()

