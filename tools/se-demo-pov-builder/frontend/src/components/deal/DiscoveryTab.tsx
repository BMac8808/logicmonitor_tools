import { useState } from "react";
import { api } from "../../api";
import type { Confidence, Priority, Question, Stakeholder } from "../../types";
import GapsList from "./GapsList";
import { attempt, Badge, ErrorBanner, StatusBadge, useAsync, useLibrary } from "../../ui";

function QuestionCard({ dealId, q, stakeholders, onSaved }: {
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

  const fieldId = `answer-${q.id}`;
  return (
    <div className="question" data-testid={`question-${q.id}`}>
      <div className="row spread">
        <label htmlFor={fieldId} className="question-text" style={{ color: "inherit", fontSize: "1rem" }}>{q.text}</label>
        <div className="row">
          <Badge>{q.category}</Badge>
          {q.priority === 1 && <Badge tone="info">key</Badge>}
          {q.answer && <StatusBadge value={q.answer.confidence} />}
        </div>
      </div>
      <p className="muted small">
        {q.purpose}
        {q.listen_for.length > 0 && <> · Listen for: {q.listen_for.join(", ")}</>}
        {q.suggests_capabilities.length > 0 && <> · Related: {q.suggests_capabilities.map(lib.capabilityName).join(", ")}</>}
      </p>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <textarea id={fieldId} value={answer} onChange={(e) => { setAnswer(e.target.value); setStatus(""); }}
        placeholder="Record what the customer said, in their words." style={{ width: "100%" }} />
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

export default function DiscoveryTab({ dealId, onChange, llmEnabled }: { dealId: number; onChange: () => void; llmEnabled: boolean }) {
  const questions = useAsync(() => api.questions(dealId), [dealId]);
  const stakeholders = useAsync(() => api.stakeholders(dealId), [dealId]);
  const gaps = useAsync(() => api.gaps(dealId), [dealId]);
  const [filter, setFilter] = useState<"all" | "unanswered">("all");
  const [draft, setDraft] = useState<{ draft: string; label: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    void questions.reload();
    void gaps.reload();
    onChange();
  };

  const qs = questions.data?.questions.filter((q) => filter === "all" || !q.answer) ?? [];

  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(280px, 1fr)" }}>
      <div className="card">
        <div className="row spread">
          <h2>Discovery questions</h2>
          <div className="row">
            <span className="muted small">{questions.data?.answered ?? 0} of {questions.data?.total ?? 0} answered</span>
            <select aria-label="Filter questions" value={filter} onChange={(e) => setFilter(e.target.value as "all" | "unanswered")}>
              <option value="all">All</option><option value="unanswered">Unanswered</option>
            </select>
          </div>
        </div>
        <p className="muted small">Questions are selected from the personas of this deal's stakeholders and its technical context.</p>
        <ErrorBanner error={questions.error} />
        {qs.map((q) => (
          <QuestionCard key={`${q.id}-${q.answer?.updated_at ?? ""}`} dealId={dealId} q={q}
            stakeholders={stakeholders.data ?? []} onSaved={refresh} />
        ))}
        {questions.data && questions.data.unmatched_answers.length > 0 && (
          <details>
            <summary>{questions.data.unmatched_answers.length} saved answer(s) to questions not currently selected</summary>
            <ul>{questions.data.unmatched_answers.map((a) => <li key={a.id}><code>{a.question_id}</code>: {a.answer}</li>)}</ul>
          </details>
        )}
      </div>
      <div>
        <div className="card">
          <h3>Qualification checklist</h3>
          <table>
            <tbody>
              {gaps.data?.qualification.map((item) => (
                <tr key={item.key}>
                  <td title={item.description}>{item.label}</td>
                  <td style={{ textAlign: "right" }}><StatusBadge value={item.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
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
                <pre className="output" style={{ whiteSpace: "pre-wrap" }}>{draft.draft}</pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
