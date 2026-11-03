import { useState } from "react";
import { api } from "../../api";
import type { Question, QuestionCategory, QuestionListProposal, TranscriptProposal, TranscriptProposals } from "../../types";
import { attempt, Badge, ErrorBanner, Generated } from "../../ui";
import { CATEGORIES } from "./categories";

type Mode = "transcript" | "list";
const ACCEPT: Record<Mode, string[]> = { transcript: [".txt", ".vtt", ".srt"], list: [".txt", ".md", ".csv"] };
const MAX_BYTES = 2_000_000;

interface Review {
  answer: string;
  state: "pending" | "accepted" | "rejected";
  error: string | null;
}

function ProposalCard({ p, review, onChange, onAccept }: {
  p: TranscriptProposal; review: Review; onChange: (r: Partial<Review>) => void; onAccept: () => void;
}) {
  const where = [p.speaker, p.timestamp].filter(Boolean).join(" · ");
  return (
    <div className={`proposal ${review.state}`} data-testid={`proposal-${p.question_id}`}>
      <div className="row spread">
        <strong>{p.question}</strong>
        <Badge tone="outline">{p.method === "ai" ? "AI suggestion" : "keyword match"}</Badge>
      </div>
      <blockquote className="quote small">
        “{p.quote}”
        <cite>{where || "Transcript"}</cite>
      </blockquote>
      {p.matched.length > 0 && <div className="small"><Generated>Matched: {p.matched.join(", ")}</Generated></div>}
      {p.existing_answer && (
        <div className="small" style={{ color: "var(--warn)" }}>
          Replaces the saved {p.existing_answer.confidence} answer: “{p.existing_answer.answer}”
        </div>
      )}
      <ErrorBanner error={review.error} onDismiss={() => onChange({ error: null })} />
      {review.state === "pending" ? (
        <>
          <label className="small" style={{ marginTop: 6 }}>
            Answer to save (edit it so it matches the quote)
            <textarea aria-label={`Proposed answer to: ${p.question}`} value={review.answer}
              onChange={(e) => onChange({ answer: e.target.value })} style={{ minHeight: "3rem" }} />
          </label>
          <div className="row" style={{ marginTop: 6 }}>
            <button type="button" onClick={onAccept} disabled={!review.answer.trim()}>Accept as assumed</button>
            <button type="button" className="secondary" onClick={() => onChange({ state: "rejected" })}>Reject</button>
          </div>
        </>
      ) : (
        <div className="row small" style={{ marginTop: 4 }}>
          {review.state === "accepted" ? <Badge tone="warn">saved as assumed</Badge> : <span className="muted">Rejected</span>}
          {review.state === "rejected" && (
            <button type="button" className="link small" onClick={() => onChange({ state: "pending" })}>Undo</button>
          )}
        </div>
      )}
    </div>
  );
}

export default function DiscoveryImport({ dealId, llmEnabled, questions, onSaved, onClose }: {
  dealId: number; llmEnabled: boolean; questions: Question[]; onSaved: () => void; onClose: () => void;
}) {
  const [mode, setMode] = useState<Mode>("transcript");
  const [text, setText] = useState("");
  const [filename, setFilename] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptProposals | null>(null);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [list, setList] = useState<(QuestionListProposal & { selected: boolean })[] | null>(null);
  const [listResult, setListResult] = useState<string | null>(null);

  const reset = () => {
    setText(""); setFilename(""); setResult(null); setReviews({}); setList(null); setListResult(null); setError(null);
  };

  const readFile = async (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPT[mode].includes(ext)) {
      setError(`Use a ${ACCEPT[mode].join(", ")} file, or paste the text.`);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("That file is over 2 MB. Paste the relevant part instead.");
      return;
    }
    setText(await file.text());
    setFilename(file.name);
    setError(null);
  };

  const key = (p: TranscriptProposal) => `${p.question_id}|${p.quote}`;

  const findAnswers = async () => {
    setBusy(true);
    await attempt(async () => {
      const r = await api.transcriptProposals(dealId, { text, filename, use_ai: useAi });
      setResult(r);
      setReviews(Object.fromEntries(r.proposals.map((p) => [key(p), { answer: p.proposed_answer, state: "pending", error: null }])));
    }, setError);
    setBusy(false);
  };

  const accept = async (p: TranscriptProposal) => {
    const review = reviews[key(p)];
    const update = (r: Partial<Review>) => setReviews((all) => ({ ...all, [key(p)]: { ...all[key(p)], ...r } }));
    const ok = await attempt(() => api.acceptTranscriptAnswer(dealId, {
      question_id: p.question_id, answer: review.answer, quote: p.quote, speaker: p.speaker, timestamp: p.timestamp, filename,
      receipt: p.receipt,
    }), (e) => update({ error: e }));
    if (ok) {
      // Only one accepted answer per question: other proposals for it are set aside.
      setReviews((all) => Object.fromEntries(Object.entries(all).map(([k, r]) =>
        [k, k === key(p) ? { ...r, state: "accepted" } : k.startsWith(`${p.question_id}|`) && r.state === "pending" ? { ...r, state: "rejected" } : r])));
      onSaved();
    }
  };

  const findQuestions = async () => {
    setBusy(true);
    await attempt(async () => {
      const r = await api.questionListProposals(dealId, text);
      setList(r.proposals.map((p) => ({ ...p, selected: p.duplicate_level !== "likely" })));
      setListResult(null);
    }, setError);
    setBusy(false);
  };

  const addQuestions = async () => {
    const chosen = (list ?? []).filter((p) => p.selected);
    await attempt(async () => {
      const r = await api.addCustomQuestions(dealId, chosen.map((p) => ({ text: p.text, category: p.category })));
      setListResult(`Added ${r.created.length} question(s)${r.skipped.length ? `; skipped ${r.skipped.length} already on this deal` : ""}.`);
      setList(null);
      onSaved();
    }, setError);
  };

  const pending = result ? result.proposals.filter((p) => reviews[key(p)]?.state === "pending").length : 0;
  const known = new Map(questions.map((q) => [q.id, q.text]));

  return (
    <div className="card" style={{ background: "var(--surface-2)" }} aria-label="Import transcript or question list">
      <div className="row spread">
        <div className="seg" role="group" aria-label="Import type">
          <button type="button" aria-pressed={mode === "transcript"} onClick={() => { setMode("transcript"); reset(); }}>Call transcript</button>
          <button type="button" aria-pressed={mode === "list"} onClick={() => { setMode("list"); reset(); }}>Question list</button>
        </div>
        <button type="button" className="link" onClick={onClose}>Close</button>
      </div>
      <p className="muted small" style={{ marginTop: 6 }}>
        {mode === "transcript"
          ? "Paste a transcript or drop a .txt, .vtt or .srt file. It is read in memory and not saved. You review each proposed answer against the exact quote; accepted answers are saved as assumed, with only that quote kept as evidence."
          : "Paste your own question list (one per line; bullets and numbers are fine). You choose which become questions on this deal."}
      </p>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <div className={`dropzone${over ? " over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) void readFile(f); }}>
        <textarea aria-label={mode === "transcript" ? "Transcript text" : "Question list text"} value={text}
          onChange={(e) => { setText(e.target.value); if (!e.target.value) setFilename(""); }}
          placeholder={mode === "transcript" ? "[00:12:31] Dana Whitlock: We get about three thousand alerts a week…" : "- What does an hour of downtime cost you?"}
          style={{ width: "100%", minHeight: "6rem" }} />
        <div className="row" style={{ justifyContent: "center", marginTop: 6 }}>
          <span className="small">Drop a file here, or</span>
          <label className="inline small" style={{ cursor: "pointer", color: "var(--accent)" }}>
            choose a file
            <input type="file" accept={ACCEPT[mode].join(",")} style={{ display: "none" }} aria-label="Choose file"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void readFile(f); e.target.value = ""; }} />
          </label>
          {filename && <Badge tone="outline">{filename}</Badge>}
        </div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        {mode === "transcript" ? (
          <>
            {llmEnabled && (
              <label className="inline small">
                <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
                Also ask AI (quotes are checked word for word against the transcript)
              </label>
            )}
            <button type="button" onClick={findAnswers} disabled={!text.trim() || busy}>{busy ? "Reading…" : "Find answers"}</button>
          </>
        ) : (
          <button type="button" onClick={findQuestions} disabled={!text.trim() || busy}>{busy ? "Reading…" : "Find questions"}</button>
        )}
        {(text || result || list) && <button type="button" className="secondary" onClick={reset}>Clear</button>}
      </div>

      {result && (
        <div style={{ marginTop: 10 }}>
          <div className="row spread">
            <strong>{result.proposals.length} proposed answer(s)</strong>
            <span className="muted small">
              {result.segments} passage(s) read ({result.format}){result.ai_used ? " · keyword matching + AI" : " · keyword matching"}
              {result.proposals.length > 0 && ` · ${pending} left to review`}
            </span>
          </div>
          {result.notes.map((n) => <p key={n} className="small muted">{n}</p>)}
          {!result.proposals.length && <p className="empty">No answers found. Try pasting a longer part of the call.</p>}
          {result.proposals.map((p) => (
            <ProposalCard key={key(p)} p={p} review={reviews[key(p)]}
              onChange={(r) => setReviews((all) => ({ ...all, [key(p)]: { ...all[key(p)], ...r } }))}
              onAccept={() => void accept(p)} />
          ))}
        </div>
      )}

      {list && (
        <div style={{ marginTop: 10 }}>
          <strong>{list.length} question(s) found</strong>
          {list.map((p, i) => (
            <div key={i} className="row" style={{ marginTop: 6, alignItems: "flex-start" }}>
              <input type="checkbox" aria-label={`Add: ${p.text}`} checked={p.selected}
                onChange={(e) => setList(list.map((x, j) => (j === i ? { ...x, selected: e.target.checked } : x)))} />
              <div style={{ flex: 1 }}>
                <input aria-label={`Question ${i + 1}`} value={p.text} style={{ width: "100%" }}
                  onChange={(e) => setList(list.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
                {p.duplicate_of && (
                  <div className="small" style={{ color: p.duplicate_level === "possible" ? "var(--muted)" : "var(--warn)" }}>
                    {p.duplicate_level === "possible" ? "Possibly similar to" : "Similar to"} an existing question:
                    {" "}“{p.duplicate_text ?? known.get(p.duplicate_of)}”
                  </div>
                )}
              </div>
              <select aria-label={`Category for question ${i + 1}`} value={p.category}
                onChange={(e) => setList(list.map((x, j) => (j === i ? { ...x, category: e.target.value as QuestionCategory } : x)))}>
                {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
          ))}
          <button type="button" style={{ marginTop: 8 }} onClick={addQuestions}
            disabled={!list.some((p) => p.selected && p.text.trim().length >= 3)}>
            Add {list.filter((p) => p.selected).length} question(s) to this deal
          </button>
        </div>
      )}
      {listResult && <p className="small" style={{ marginTop: 8 }}>{listResult}</p>}
    </div>
  );
}
