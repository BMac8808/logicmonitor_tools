import { useEffect, useState } from "react";
import { api } from "../../api";
import type { DemoPlan } from "../../types";
import {
  attempt, CapabilityChip, downloadText, Empty, ErrorBanner, Generated, slug, StatusBadge, Tile, UnverifiedNotice, useAsync,
} from "../../ui";

function List({ items, empty = "None" }: { items: string[]; empty?: string }) {
  return items.length ? <ul className="gen">{items.map((i) => <li key={i}>{i}</li>)}</ul> : <p className="empty">{empty}</p>;
}

function PlanView({ plan }: { plan: DemoPlan }) {
  const c = plan.content;
  const caps = new Map(c.segments.flatMap((s) => s.capabilities).map((cap) => [cap.id, cap]));
  const unverified = [...caps.values()].filter((cap) => !cap.verified).length;
  // Must/should requirements, like uncovered_requirements.
  const covered = new Set(c.segments.flatMap((s) => s.linked_requirements.filter((r) => r.priority !== "could").map((r) => r.id)));
  const tracked = covered.size + c.uncovered_requirements.length;
  const scheduled = c.agenda.reduce((sum, a) => sum + a.minutes, 0);
  return (
    <div>
      {c.generic && (
        <div className="banner banner-warn">Generic plan: no discovery finding matched a scenario. Complete discovery to tailor it.</div>
      )}
      <div className="tiles" aria-label="Demo plan summary">
        <Tile tone="info" value={c.segments.length} label="Scenarios" />
        <Tile tone={scheduled === plan.duration_minutes ? "good" : "warn"} value={`${scheduled}/${plan.duration_minutes}`} label="Minutes scheduled" />
        <Tile tone={c.uncovered_requirements.length ? "warn" : "good"} value={`${covered.size}/${tracked}`}
          label="Requirements covered" hint="Must/should requirements shown by at least one scenario" />
        <Tile tone={c.uncovered_requirements.length ? "warn" : "good"} value={c.uncovered_requirements.length} label="Not covered" />
        <Tile tone={unverified ? "warn" : "good"} value={unverified} label="Unverified capabilities" />
        <Tile tone={c.missing_evidence.length ? "warn" : "good"} value={c.missing_evidence.length} label="Missing evidence" />
      </div>
      {c.uncovered_requirements.length > 0 && (
        <div className="callout callout-warn" role="note" aria-label="Requirements not covered">
          <h4>{c.uncovered_requirements.length} requirement(s) not covered by this demo</h4>
          <ul>{c.uncovered_requirements.map((r) => <li key={r.id}><StatusBadge value={r.priority} /> {r.title}</li>)}</ul>
          <div className="small">Add a scenario that shows them, cover them in the POV, or agree with the customer that they're out of scope.</div>
        </div>
      )}
      <div className="grid grid-2">
        <div className="card">
          <h3>Agenda ({plan.duration_minutes} min)</h3>
          <table className="agenda gen">
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
              <strong>{a.persona}</strong> ({a.stakeholders.join(", ")}): <Generated>{a.focus.join("; ")}</Generated>
            </div>
          )) : <Empty>No stakeholders recorded.</Empty>}
        </div>
      </div>
      <div className="card">
        <h3>Scenarios</h3>
        <p className="muted small" style={{ marginBottom: 2 }}>
          Customer pain points and stakeholder names are yours; <Generated>italic text</Generated> is generated from the scenario library.
        </p>
        <UnverifiedNotice count={unverified} total={caps.size} />
        {c.segments.map((s) => (
          <div key={s.scenario_id} className="segment">
            <div className="row spread">
              <h4>{s.title} <span className="muted">· {s.minutes} min</span></h4>
              <div className="chips">
                {s.capabilities.map((cap) => <CapabilityChip key={cap.id} name={cap.name} verified={cap.verified} />)}
              </div>
            </div>
            <p className="gen">{s.summary}</p>
            {s.linked_requirements.length > 0 && (
              <p className="small">Shows: {s.linked_requirements.map((r) => r.title).join(" · ")}</p>
            )}
            <p className="small"><span className="muted">Why:</span> <Generated>{s.selection_reason}</Generated></p>
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
                    <ul className="gen">{tp.points.map((p) => <li key={p}>{p}</li>)}</ul>
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
      <div className="grid grid-2">
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
