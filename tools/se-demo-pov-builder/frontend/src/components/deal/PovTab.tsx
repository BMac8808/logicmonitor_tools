import { useEffect, useState } from "react";
import { api } from "../../api";
import type { Criterion, CriterionStatus, PovPlan, Requirement } from "../../types";
import PortalSetupCard from "./PortalSetupCard";
import TaskTable from "./TaskTable";
import { attempt, downloadText, Empty, ErrorBanner, SimulatedBadge, slug, StatusBadge, useAsync } from "../../ui";

const CRITERION_STATUSES: CriterionStatus[] = ["not_started", "in_progress", "met", "not_met", "waived"];
const EVIDENCE_TYPES = ["observation", "screenshot", "document", "metric", "customer_confirmation"];
const blankCriterion = { title: "", requirement_id: "", measurable_outcome: "", target: "", validation_method: "", owner: "" };

function CreatePov({ dealId, onCreated }: { dealId: number; onCreated: (p: PovPlan) => void }) {
  const [form, setForm] = useState({
    title: "", objectives: "", start_date: new Date().toISOString().slice(0, 10), duration_days: 30, draft: true,
  });
  const [error, setError] = useState<string | null>(null);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    return attempt(async () => onCreated(await api.createPovPlan(dealId, {
      title: form.title, objectives: form.objectives, start_date: form.start_date,
      duration_days: form.duration_days, draft_criteria_from_requirements: form.draft,
    })), setError);
  };
  return (
    <form className="card" onSubmit={submit} aria-label="Create POV plan">
      <h2>Create a POV plan</h2>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <div className="form-grid">
        <label>Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label>Start date<input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label>
        <label>Duration (days)<input type="number" min={1} max={180} value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: Number(e.target.value) })} /></label>
        <label className="full">Objectives<textarea value={form.objectives} onChange={(e) => setForm({ ...form, objectives: e.target.value })} /></label>
        <label className="inline full">
          <input type="checkbox" checked={form.draft} onChange={(e) => setForm({ ...form, draft: e.target.checked })} />
          Draft success criteria for must/should requirements that have none
        </label>
      </div>
      <button type="submit" style={{ marginTop: 8 }}>Create POV plan</button>
      <p className="muted small" style={{ marginTop: 8 }}>Milestones come from <code>knowledge/pov_template.yaml</code>.</p>
    </form>
  );
}

function CriterionCard({ c, reqs, onChange }: { c: Criterion; reqs: Requirement[]; onChange: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(!c.measurable_outcome || !c.validation_method);
  const [form, setForm] = useState({
    title: c.title, measurable_outcome: c.measurable_outcome, target: c.target,
    validation_method: c.validation_method, owner: c.owner,
  });
  const [ev, setEv] = useState({ description: "", reference: "", evidence_type: "observation", is_simulated: false, recorded_by: "" });
  const req = reqs.find((r) => r.id === c.requirement_id);
  const real = c.evidence.filter((e) => !e.is_simulated).length;

  const update = async (body: Partial<Criterion>) => {
    if (await attempt(() => api.updateCriterion(c.id, body), setError)) onChange();
  };
  const addEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await attempt(() => api.addEvidence(c.id, ev), setError)) {
      setEv({ ...ev, description: "", reference: "" });
      onChange();
    }
  };

  return (
    <div className="card" data-testid={`criterion-${c.id}`}>
      <div className="row spread">
        <div>
          <h3 style={{ marginBottom: 2 }}>{c.title}</h3>
          <div className="muted small">{req ? <>Requirement: {req.title} <StatusBadge value={req.priority} /></> : "Not linked to a requirement"}</div>
        </div>
        <div className="row">
          <select aria-label={`Status for ${c.title}`} value={c.status} onChange={(e) => update({ status: e.target.value as CriterionStatus })}>
            {CRITERION_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
          <button type="button" className="link small" onClick={() => setEditing((v) => !v)}>{editing ? "Close" : "Edit"}</button>
        </div>
      </div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {c.notes && <p className="small muted">{c.notes}</p>}
      {editing ? (
        <div className="form-grid">
          <label className="full">Title<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label className="full">Measurable outcome<input value={form.measurable_outcome} onChange={(e) => setForm({ ...form, measurable_outcome: e.target.value })} placeholder="e.g. 95% of pilot devices report metrics" /></label>
          <label>Target<input value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} /></label>
          <label>Owner (validator)<input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></label>
          <label className="full">Validation method<input value={form.validation_method} onChange={(e) => setForm({ ...form, validation_method: e.target.value })} /></label>
          <div><button type="button" onClick={async () => { await update(form); setEditing(false); }}>Save criterion</button></div>
        </div>
      ) : (
        <table className="small">
          <tbody>
            <tr><th>Outcome</th><td>{c.measurable_outcome}</td></tr>
            <tr><th>Target</th><td>{c.target || "—"}</td></tr>
            <tr><th>Validation</th><td>{c.validation_method}</td></tr>
            <tr><th>Owner</th><td>{c.owner || "—"}</td></tr>
          </tbody>
        </table>
      )}
      <h4 style={{ marginTop: 10 }}>Evidence ({real} real{c.evidence.length - real ? `, ${c.evidence.length - real} simulated` : ""})</h4>
      {c.evidence.length ? (
        <ul className="small">
          {c.evidence.map((e) => (
            <li key={e.id}>
              {e.is_simulated && <><SimulatedBadge />{" "}</>}
              {e.description}{e.reference && <span className="muted"> · {e.reference}</span>}
              <span className="muted"> · {e.evidence_type}{e.recorded_by && ` · ${e.recorded_by}`}</span>{" "}
              <button type="button" className="link" onClick={() => attempt(() => api.deleteEvidence(e.id), setError).then((ok) => ok && onChange())}>remove</button>
            </li>
          ))}
        </ul>
      ) : <p className="empty small">No evidence yet. A criterion can only be marked met with real evidence.</p>}
      <form className="row" onSubmit={addEvidence} aria-label={`Add evidence for ${c.title}`}>
        <input required aria-label="Evidence description" placeholder="What was observed or confirmed" value={ev.description} onChange={(e) => setEv({ ...ev, description: e.target.value })} style={{ flex: 2 }} />
        <input aria-label="Evidence reference" placeholder="Reference / location" value={ev.reference} onChange={(e) => setEv({ ...ev, reference: e.target.value })} style={{ flex: 1 }} />
        <select aria-label="Evidence type" value={ev.evidence_type} onChange={(e) => setEv({ ...ev, evidence_type: e.target.value })}>
          {EVIDENCE_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
        </select>
        <input aria-label="Recorded by" placeholder="Recorded by" value={ev.recorded_by} onChange={(e) => setEv({ ...ev, recorded_by: e.target.value })} style={{ width: 130 }} />
        <label className="inline small"><input type="checkbox" checked={ev.is_simulated} onChange={(e) => setEv({ ...ev, is_simulated: e.target.checked })} />Simulated</label>
        <button type="submit" className="secondary">Add evidence</button>
      </form>
    </div>
  );
}

function PovDetail({ plan, reqs, reload }: { plan: PovPlan; reqs: Requirement[]; reload: () => void }) {
  const s = plan.summary;
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(blankCriterion);

  const addCriterion = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await attempt(() => api.createCriterion(plan.deal_id, {
      ...form, pov_plan_id: plan.id, requirement_id: form.requirement_id ? Number(form.requirement_id) : null,
    }), setError);
    if (ok) {
      setForm(blankCriterion);
      reload();
    }
  };

  return (
    <div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <div className="card">
        <div className="row spread">
          <div>
            <h2 style={{ marginBottom: 2 }}>{plan.title}</h2>
            <div className="muted small">{plan.start_date} → {plan.end_date}</div>
          </div>
          <div className="row">
            <select aria-label="POV status" value={plan.status}
              onChange={(e) => attempt(() => api.updatePovPlan(plan.id, { status: e.target.value as PovPlan["status"] }), setError).then((ok) => ok && reload())}>
              {["draft", "active", "completed", "closed"].map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <button type="button" className="secondary"
              onClick={() => attempt(async () => downloadText(`${slug(plan.title)}.md`, await api.exportPovPlan(plan.id)), setError)}>
              Export plan &amp; success summary
            </button>
          </div>
        </div>
        {plan.objectives && <p style={{ marginTop: 8 }}>{plan.objectives}</p>}
        <div className="metrics" style={{ marginTop: 8 }}>
          <div className="metric"><div className="value">{s.criteria_met}/{s.criteria_total}</div><div className="label">Criteria met</div></div>
          <div className="metric"><div className="value">{s.must_have_met}/{s.must_have_total}</div><div className="label">Must-have met</div></div>
          <div className="metric"><div className="value">{s.milestones_closed}/{s.milestones_total}</div><div className="label">Milestones closed</div></div>
          <div className="metric"><div className="value">{s.evidence_real}</div><div className="label">Real evidence items</div></div>
          {s.evidence_simulated > 0 && (
            <div className="metric"><div className="value">{s.evidence_simulated}</div><div className="label">Simulated (not counted)</div></div>
          )}
        </div>
        <div className="progress" aria-label="Criteria completion"><span style={{ width: `${Math.round(s.completion * 100)}%` }} /></div>
      </div>

      <div className="card">
        <h2>Technical validation checklist</h2>
        <table>
          <thead><tr><th>Requirement / criterion</th><th>Validation</th><th>Owner</th><th>Evidence</th><th>Status</th></tr></thead>
          <tbody>
            {plan.checklist.flatMap((g) => [
              <tr key={`g-${g.requirement_id ?? "none"}`}><td colSpan={5}><strong>{g.requirement}</strong> {g.priority && <StatusBadge value={g.priority} />}</td></tr>,
              ...g.items.map((i) => (
                <tr key={i.criterion_id}>
                  <td style={{ paddingLeft: 20 }}>{i.title} {!i.ready && <StatusBadge value="draft" />}</td>
                  <td className="small">{i.validation_method || <span className="muted">TBD</span>}</td>
                  <td className="small">{i.owner || "—"}</td>
                  <td className="small">{i.evidence.real} real{i.evidence.simulated ? ` · ${i.evidence.simulated} sim.` : ""}</td>
                  <td><StatusBadge value={i.status} /></td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
        {!plan.checklist.length && <Empty>No success criteria yet.</Empty>}
      </div>

      <h2>Success criteria</h2>
      {plan.criteria.map((c) => <CriterionCard key={`${c.id}-${c.status}-${c.evidence.length}`} c={c} reqs={reqs} onChange={reload} />)}
      <form className="card" onSubmit={addCriterion} aria-label="Add success criterion">
        <h3>Add success criterion</h3>
        <div className="form-grid">
          <label className="full">Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>
            Requirement
            <select value={form.requirement_id} onChange={(e) => setForm({ ...form, requirement_id: e.target.value })}>
              <option value="">None</option>
              {reqs.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
            </select>
          </label>
          <label>Owner (validator)<input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></label>
          <label className="full">Measurable outcome<input value={form.measurable_outcome} onChange={(e) => setForm({ ...form, measurable_outcome: e.target.value })} /></label>
          <label>Target<input value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} /></label>
          <label>Validation method<input value={form.validation_method} onChange={(e) => setForm({ ...form, validation_method: e.target.value })} /></label>
        </div>
        <button type="submit" style={{ marginTop: 8 }}>Add criterion</button>
      </form>

      <PortalSetupCard key={`${plan.id}-${plan.portal_group}`} plan={plan} reload={reload} />

      <div className="card">
        <h2>Milestones</h2>
        <TaskTable tasks={plan.milestones} onChange={reload} />
      </div>
    </div>
  );
}

export default function PovTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const plans = useAsync(() => api.povPlans(dealId), [dealId]);
  const reqs = useAsync(() => api.requirements(dealId), [dealId]);
  const [selected, setSelected] = useState<number | null>(null);
  const [plan, setPlan] = useState<PovPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selected === null && plans.data?.length) setSelected(plans.data[0].id);
  }, [plans.data, selected]);
  const load = async (id: number) => attempt(async () => setPlan(await api.povPlan(id)), setError);
  useEffect(() => {
    if (selected !== null) void load(selected);
  }, [selected]);

  const reload = () => {
    if (selected !== null) void load(selected);
    onChange();
  };

  return (
    <div>
      <ErrorBanner error={error ?? plans.error} onDismiss={() => setError(null)} />
      <div className="banner banner-info small">
        Never present simulated results as evidence. Simulated items are labelled and excluded from success counts and exports.
      </div>
      {plans.data && plans.data.length > 1 && (
        <select aria-label="POV plan" value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))} style={{ marginBottom: 12 }}>
          {plans.data.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
      )}
      {plans.data && !plans.data.length && (
        <CreatePov dealId={dealId} onCreated={(p) => { void plans.reload(); setSelected(p.id); setPlan(p); onChange(); }} />
      )}
      {plan && <PovDetail plan={plan} reqs={reqs.data ?? []} reload={reload} />}
    </div>
  );
}
