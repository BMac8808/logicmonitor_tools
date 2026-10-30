import { useEffect, useState } from "react";
import { api } from "../../api";
import type { DemoPlan } from "../../types";
import { attempt, Badge, downloadText, Empty, ErrorBanner, slug, StatusBadge, useAsync } from "../../ui";

function List({ items, empty = "None" }: { items: string[]; empty?: string }) {
  return items.length ? <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul> : <p className="empty">{empty}</p>;
}

function PlanView({ plan }: { plan: DemoPlan }) {
  const c = plan.content;
  return (
    <div>
      {c.generic && (
        <div className="banner banner-warn">Generic plan: no discovery finding matched a scenario. Complete discovery to tailor it.</div>
      )}
      <div className="grid grid-2">
        <div className="card">
          <h3>Agenda ({plan.duration_minutes} min)</h3>
          <table className="agenda">
            <tbody>
              {c.agenda.map((a) => (
                <tr key={`${a.start_minute}-${a.title}`}>
                  <td>+{a.start_minute}′</td><td>{a.title}</td><td className="muted">{a.minutes} min</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Customer pain points</h3>
          {c.pain_points.length ? (
            <ul>{c.pain_points.map((p) => <li key={p.requirement_id}><StatusBadge value={p.priority} /> <strong>{p.requirement}</strong>: {p.pain_point}</li>)}</ul>
          ) : <Empty>No pain points recorded on requirements.</Empty>}
          <h3>Audience</h3>
          {c.audience_focus.length ? c.audience_focus.map((a) => (
            <div key={a.persona_id} className="small" style={{ marginBottom: 6 }}>
              <strong>{a.persona}</strong> ({a.stakeholders.join(", ")}): {a.focus.join("; ")}
            </div>
          )) : <Empty>No stakeholders recorded.</Empty>}
        </div>
      </div>
      <div className="card">
        <h3>Scenarios</h3>
        {c.segments.map((s) => (
          <div key={s.scenario_id} className="segment">
            <div className="row spread">
              <h4>{s.title} <span className="muted">· {s.minutes} min</span></h4>
              <div className="chips">
                {s.capabilities.map((cap) => (
                  <Badge key={cap.id} tone={cap.verified ? "good" : "neutral"}>{cap.name}{cap.verified ? "" : " · unverified"}</Badge>
                ))}
              </div>
            </div>
            <p>{s.summary}</p>
            <p className="small muted">Why: {s.selection_reason}</p>
            <div className="grid grid-2">
              <div>
                <h4>Demonstrates</h4>
                <List items={s.demonstrates} />
              </div>
              <div>
                <h4>Talking points</h4>
                {s.talking_points.map((tp) => (
                  <div key={tp.audience} className="small">
                    <em>{tp.audience}{tp.stakeholders.length ? ` — ${tp.stakeholders.join(", ")}` : ""}</em>
                    <ul>{tp.points.map((p) => <li key={p}>{p}</li>)}</ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-3">
        <div className="card"><h3>Prerequisites</h3><List items={c.prerequisites} /></div>
        <div className="card"><h3>Data requirements</h3><List items={c.data_requirements} /></div>
        <div className="card"><h3>Preparation tasks</h3><List items={c.prep_tasks} /></div>
      </div>
      <div className="grid grid-3">
        <div className="card">
          <h3>Not covered by this demo</h3>
          <List items={c.uncovered_requirements.map((r) => `${r.title} (${r.priority})`)} empty="All must/should requirements are covered." />
        </div>
        <div className="card"><h3>Assumptions</h3><List items={c.assumptions} /></div>
        <div className="card"><h3>Missing evidence</h3><List items={c.missing_evidence} /></div>
      </div>
    </div>
  );
}

export default function DemoPlanTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const plans = useAsync(() => api.demoPlans(dealId), [dealId]);
  const [selected, setSelected] = useState<number | null>(null);
  const [plan, setPlan] = useState<DemoPlan | null>(null);
  const [duration, setDuration] = useState(60);
  const [maxScenarios, setMaxScenarios] = useState(4);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selected === null && plans.data?.length) setSelected(plans.data[0].id);
  }, [plans.data, selected]);
  useEffect(() => {
    if (selected !== null) void attempt(async () => setPlan(await api.demoPlan(selected)), setError);
  }, [selected]);

  const generate = (e: React.FormEvent) => {
    e.preventDefault();
    return attempt(async () => {
      const p = await api.generateDemoPlan(dealId, { duration_minutes: duration, max_scenarios: maxScenarios });
      await plans.reload();
      setSelected(p.id);
      setPlan(p);
      onChange();
    }, setError);
  };

  return (
    <div>
      <ErrorBanner error={error ?? plans.error} onDismiss={() => setError(null)} />
      <form className="card row spread" onSubmit={generate} aria-label="Generate demo plan">
        <div className="row">
          <label className="inline">Duration (min)
            <input type="number" min={25} max={240} value={duration} onChange={(e) => setDuration(Number(e.target.value))} style={{ width: 80 }} />
          </label>
          <label className="inline">Max scenarios
            <input type="number" min={1} max={10} value={maxScenarios} onChange={(e) => setMaxScenarios(Number(e.target.value))} style={{ width: 70 }} />
          </label>
          <button type="submit">Generate demo plan</button>
        </div>
        {plans.data && plans.data.length > 0 && (
          <div className="row">
            <select aria-label="Plan version" value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
              {plans.data.map((p) => <option key={p.id} value={p.id}>v{p.version} · {p.duration_minutes} min · {new Date(p.created_at).toLocaleString()}</option>)}
            </select>
            {plan && (
              <button type="button" className="secondary"
                onClick={() => attempt(async () => downloadText(`${slug(plan.title)}.md`, await api.exportDemoPlan(plan.id)), setError)}>
                Export Markdown
              </button>
            )}
          </div>
        )}
      </form>
      <p className="muted small">Plans are generated from saved stakeholders, discovery answers and requirements only. Each generation is saved as a new version.</p>
      {plan ? <PlanView plan={plan} /> : plans.data && !plans.data.length && <Empty>No demo plan yet. Generate one from the saved discovery.</Empty>}
    </div>
  );
}
