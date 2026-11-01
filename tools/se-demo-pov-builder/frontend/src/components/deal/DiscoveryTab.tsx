import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Confidence, Priority, Question, QuestionCategory, Stakeholder } from "../../types";
import { CATEGORIES } from "./categories";
import DiscoveryImport from "./DiscoveryImport";
import GapsList from "./GapsList";
import { attempt, Badge, ErrorBanner, Generated, StatusBadge, useAsync, useLibrary } from "../../ui";

type View = "suggested" | "all" | "unanswered" | "assumed";
const VIEWS: { id: View; label: string }[] = [
  { id: "suggested", label: "For this deal" },
  { id: "unanswered", label: "Unanswered" },
  { id: "assumed", label: "Assumed" },
  { id: "all", label: "All questions" },
];

const inScope = (q: Question) => q.suggested || q.custom || q.answer !== null;
const answerTone = (q: Question) => (q.answer ? (q.answer.confidence === "confirmed" ? "good" : "warn") : "neutral");

function QuestionEditor({ dealId, q, stakeholders, onSaved }: {
  dealId: number; q: Question; stakeholders: Stakeholder[]; onSaved: () => void;
}) {
  const lib = useLibrary();
  const [answer, setAnswer] = useState(q.answer?.answer ?? "");
  const [stakeholderId, setStakeholderId] = useState<string>(q.answer?.stakeholder_id ? String(q.answer.stakeholder_id) : "");
  const [source, setSource] = useState(q.answer?.evidence_source ?? "");
  const [confidence, setConfidence] = useState<Confidence>(q.answer?.confidence ?? "confirmed");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [reqOpen, setReqOpen] = useState(false);
  const [reqTitle, setReqTitle] = useState("");
  const [reqPriority, setReqPriority] = useState<Priority>("should");

  const dirty = answer !== (q.answer?.answer ?? "") || source !== (q.answer?.evidence_source ?? "")
    || confidence !== (q.answer?.confidence ?? "confirmed")
    || stakeholderId !== (q.answer?.stakeholder_id ? String(q.answer.stakeholder_id) : "");

  const save = async () => {
    const ok = await attempt(() => api.saveAnswer(dealId, q.id, {
      answer, evidence_source: source, confidence, stakeholder_id: stakeholderId ? Number(stakeholderId) : null,
      // Keep the transcript quote only while the answer still comes from it.
      evidence_quote: source === (q.answer?.evidence_source ?? "") ? q.answer?.evidence_quote ?? null : null,
    }), setError);
    if (ok) {
      setStatus("Saved");
      onSaved();
    }
  };

  const createRequirement = async () => {
    const ok = await attempt(() => api.createRequirement(dealId, {
      title: reqTitle, priority: reqPriority, pain_point: answer, source_question_id: q.id,
      capability_ids: null, category: q.category === "business" ? "business" : "technical",
    }), setError);
    if (ok) {
      setReqOpen(false);
      setReqTitle("");
      setStatus("Requirement created (see Requirements tab)");
      onSaved();
    }
  };

  const removeCustom = async () => {
    if (!window.confirm(`Delete this question${q.answer ? " and its saved answer" : ""}?`)) return;
    if (await attempt(() => api.deleteCustomQuestion(dealId, q.id), setError)) onSaved();
  };

  return (
    <div className="q-detail" data-testid={`question-${q.id}`}>
      {(q.purpose || q.listen_for.length > 0 || q.suggests_capabilities.length > 0) && (
        <p className="muted small">
          {q.purpose}
          {q.listen_for.length > 0 && <> · Listen for: {q.listen_for.join(", ")}</>}
          {q.suggests_capabilities.length > 0 && <> · Related: {q.suggests_capabilities.map(lib.capabilityName).join(", ")}</>}
        </p>
      )}
      {q.answer?.evidence_quote && (
        <blockquote className="quote small">
          “{q.answer.evidence_quote}”
          <cite>{q.answer.evidence_source || "Call transcript"}</cite>
        </blockquote>
      )}
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <textarea aria-label={`Answer to: ${q.text}`} value={answer} onChange={(e) => { setAnswer(e.target.value); setStatus(""); }}
        placeholder="Record what the customer said, in their words." />
      <div className="row" style={{ marginTop: 6 }}>
        <select aria-label="Answered by" value={stakeholderId} onChange={(e) => setStakeholderId(e.target.value)}>
          <option value="">Answered by…</option>
          {stakeholders.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input aria-label="Evidence source" placeholder="Source (e.g. call on 3 Oct)" value={source}
          onChange={(e) => setSource(e.target.value)} />
        <select aria-label="Confidence" value={confidence} onChange={(e) => setConfidence(e.target.value as Confidence)}>
          <option value="confirmed">Confirmed by customer</option>
          <option value="assumed">Assumed / unconfirmed</option>
        </select>
        <button type="button" onClick={save} disabled={!answer.trim() || !dirty}>Save answer</button>
        {q.answer && (
          <button type="button" className="secondary" onClick={() => setReqOpen((v) => !v)}>→ Requirement</button>
        )}
        {q.custom && <button type="button" className="danger" onClick={removeCustom}>Delete question</button>}
        {status && <span className="muted small">{status}</span>}
      </div>
      {reqOpen && (
        <div className="row" style={{ marginTop: 6 }}>
          <input aria-label="Requirement title" placeholder="Requirement title" value={reqTitle}
            onChange={(e) => setReqTitle(e.target.value)} style={{ flex: 1 }} />
          <select aria-label="Requirement priority" value={reqPriority} onChange={(e) => setReqPriority(e.target.value as Priority)}>
            <option value="must">Must</option><option value="should">Should</option><option value="could">Could</option>
          </select>
          <button type="button" onClick={createRequirement} disabled={!reqTitle.trim()}>Create requirement</button>
        </div>
      )}
    </div>
  );
}

function QuestionRow({ q, open, onToggle, children }: { q: Question; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div id={`q-${q.id}`} className={`q-item${open ? " open" : ""}`}>
      <button type="button" className={`q-row${inScope(q) ? "" : " dim"}`} aria-expanded={open} onClick={onToggle}
        title={q.answer ? `Answer (${q.answer.confidence}): ${q.answer.answer}` : "Not answered yet"}>
        <span className="chev" aria-hidden>{open ? "▾" : "▸"}</span>
        <span className={`dot dot-${answerTone(q)}`} aria-label={q.answer ? q.answer.confidence : "not answered"} />
        <span className="q-text">{q.text}</span>
        {q.custom && <Badge tone="outline">custom</Badge>}
        {q.priority === 1 && !q.custom && <Badge tone="outline">key</Badge>}
        {!q.suggested && !q.custom && <span className="muted small">not suggested</span>}
      </button>
      {open && children}
    </div>
  );
}

function AddQuestion({ dealId, onAdded }: { dealId: number; onAdded: (id: string) => void }) {
  const lib = useLibrary();
  const [text, setText] = useState("");
  const [category, setCategory] = useState<QuestionCategory>("business");
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    let created = "";
    const ok = await attempt(async () => {
      created = (await api.addCustomQuestion(dealId, { text, category, qualification_key: key || null })).id;
    }, setError);
    if (ok) {
      setText("");
      onAdded(created);
    }
  };
  return (
    <form className="row" onSubmit={submit} aria-label="Add a question for this deal" style={{ margin: "0.4rem 0" }}>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <input aria-label="New question" placeholder="Your own question for this deal" value={text}
        onChange={(e) => setText(e.target.value)} style={{ flex: 1, minWidth: 220 }} required minLength={3} />
      <select aria-label="New question category" value={category} onChange={(e) => setCategory(e.target.value as QuestionCategory)}>
        {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select>
      <select aria-label="Checklist item" value={key} onChange={(e) => setKey(e.target.value)}>
        <option value="">No checklist item</option>
        {lib.discovery.qualification_checklist.map((i) => <option key={i.key} value={i.key}>{i.label}</option>)}
      </select>
      <button type="submit" disabled={text.trim().length < 3}>Add question</button>
    </form>
  );
}

export default function DiscoveryTab({ dealId, onChange, llmEnabled }: { dealId: number; onChange: () => void; llmEnabled: boolean }) {
  const questions = useAsync(() => api.questions(dealId), [dealId]);
  const stakeholders = useAsync(() => api.stakeholders(dealId), [dealId]);
  const gaps = useAsync(() => api.gaps(dealId), [dealId]);
  const [view, setView] = useState<View>("suggested");
  const [search, setSearch] = useState("");
  const [checklistKey, setChecklistKey] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [panel, setPanel] = useState<"none" | "add" | "import">("none");
  const [draft, setDraft] = useState<{ draft: string; label: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    void questions.reload();
    void gaps.reload();
    onChange();
  };

  const all = questions.data?.questions ?? [];
  const byId = useMemo(() => new Map(all.map((q) => [q.id, q])), [all]);
  const checklistItem = gaps.data?.qualification.find((i) => i.key === checklistKey) ?? null;

  const term = search.trim().toLowerCase();
  const visible = all.filter((q) => {
    if (checklistItem) {
      if (!checklistItem.question_ids.includes(q.id)) return false;
    } else if (view === "suggested" && !inScope(q)) return false;
    else if (view === "unanswered" && (q.answer || !(q.suggested || q.custom))) return false;
    else if (view === "assumed" && q.answer?.confidence !== "assumed") return false;
    return !term || q.text.toLowerCase().includes(term) || (q.answer?.answer.toLowerCase().includes(term) ?? false);
  });

  const reveal = (id: string) => {
    const q = byId.get(id);
    setChecklistKey(null);
    setSearch("");
    if (q && !inScope(q)) setView("all");
    else if (view === "assumed" && !q?.answer) setView("suggested");
    setOpenId(id);
  };
  useEffect(() => {
    if (openId) document.getElementById(`q-${openId}`)?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [openId]);

  const next = (questions.data?.next_up ?? []).filter((n) => byId.has(n.question_id));
  const d = questions.data;

  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(260px, 1fr)" }}>
      <div>
        {next.length > 0 && (
          <div className="card start-here" aria-label="Start here">
            <h3>Start here</h3>
            <p className="muted small" style={{ marginBottom: 2 }}>The next questions worth asking, based on what's still missing.</p>
            <ol>
              {next.map((n) => (
                <li key={n.question_id}>
                  <button type="button" className="link" onClick={() => reveal(n.question_id)}>{byId.get(n.question_id)?.text}</button>
                  <div><Generated>{n.reason}</Generated></div>
                </li>
              ))}
            </ol>
          </div>
        )}

        <div className="card">
          <div className="row spread">
            <h2 style={{ marginBottom: 0 }}>Discovery questions</h2>
            <span className="muted small">
              {d?.answered ?? 0} of {d?.total ?? 0} answered for this deal · {d?.bank_total ?? 0} in the question bank
            </span>
          </div>
          <div className="toolbar">
            <div className="seg" role="group" aria-label="Show questions">
              {VIEWS.map((v) => (
                <button key={v.id} type="button" aria-pressed={!checklistItem && view === v.id}
                  onClick={() => { setView(v.id); setChecklistKey(null); }}>{v.label}</button>
              ))}
            </div>
            <input type="search" aria-label="Search questions" placeholder="Search questions and answers"
              value={search} onChange={(e) => setSearch(e.target.value)} />
            <button type="button" className={panel === "add" ? "" : "secondary"} onClick={() => setPanel(panel === "add" ? "none" : "add")}>+ Question</button>
            <button type="button" className={panel === "import" ? "" : "secondary"} onClick={() => setPanel(panel === "import" ? "none" : "import")}>Import transcript / list</button>
          </div>
          {checklistItem && (
            <div className="banner banner-info small" style={{ marginBottom: 6 }}>
              <span>Showing questions for checklist item <strong>{checklistItem.label}</strong> ({checklistItem.question_ids.length}).</span>
              <button type="button" className="link" onClick={() => setChecklistKey(null)}>Show all</button>
            </div>
          )}
          {panel === "add" && <AddQuestion dealId={dealId} onAdded={(id) => { refresh(); setView("suggested"); setOpenId(id); }} />}
          {panel === "import" && (
            <DiscoveryImport dealId={dealId} llmEnabled={llmEnabled} questions={all}
              onSaved={refresh} onClose={() => setPanel("none")} />
          )}
          <ErrorBanner error={questions.error} />
          {view === "suggested" && !checklistItem && (
            <p className="muted small" style={{ margin: "0.3rem 0 0" }}>
              Picked for this deal's stakeholders and technologies, plus your own questions and anything already answered.
              Choose <em>All questions</em> to browse the whole bank.
            </p>
          )}
          {CATEGORIES.map((cat) => {
            const items = visible.filter((q) => q.category === cat.id);
            if (!items.length) return null;
            return (
              <section key={cat.id} className="q-group" aria-label={`${cat.label} questions`}>
                <h3>{cat.label}<span className="count">{items.filter((q) => q.answer).length}/{items.length}</span></h3>
                {items.map((q) => (
                  <QuestionRow key={q.id} q={q} open={openId === q.id} onToggle={() => setOpenId(openId === q.id ? null : q.id)}>
                    <QuestionEditor key={`${q.id}-${q.answer?.updated_at ?? ""}`} dealId={dealId} q={q}
                      stakeholders={stakeholders.data ?? []} onSaved={refresh} />
                  </QuestionRow>
                ))}
              </section>
            );
          })}
          {d && !visible.length && <p className="empty">No questions match.</p>}
          {d && d.unmatched_answers.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary>{d.unmatched_answers.length} saved answer(s) to questions that no longer exist</summary>
              <ul>{d.unmatched_answers.map((a) => <li key={a.id}><code>{a.question_id}</code>: {a.answer}</li>)}</ul>
            </details>
          )}
        </div>
      </div>
      <div>
        <div className="card">
          <h3>Qualification checklist</h3>
          <p className="muted small" style={{ marginBottom: 4 }}>Click an item to see its questions.</p>
          {gaps.data?.qualification.map((item) => (
            <button key={item.key} type="button" className="checklist-row" title={item.description}
              aria-pressed={checklistKey === item.key}
              onClick={() => { setChecklistKey(checklistKey === item.key ? null : item.key); setSearch(""); }}>
              <span>{item.label}</span>
              <StatusBadge value={item.status} />
            </button>
          ))}
        </div>
        <div className="card">
          <h3>Gaps &amp; suggested next actions</h3>
          {gaps.data && <GapsList dealId={dealId} gaps={gaps.data.gaps} onChange={onChange} />}
        </div>
        {llmEnabled && (
          <div className="card">
            <h3>Optional: AI discovery summary</h3>
            <ErrorBanner error={error} onDismiss={() => setError(null)} />
            <button type="button" className="secondary"
              onClick={() => attempt(async () => setDraft(await api.llmSummary(dealId)), setError)}>
              Draft summary
            </button>
            {draft && (
              <>
                <div className="banner banner-warn" style={{ marginTop: 8 }}>{draft.label}</div>
                <Generated block label="AI draft"><div style={{ whiteSpace: "pre-wrap" }} className="small">{draft.draft}</div></Generated>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
