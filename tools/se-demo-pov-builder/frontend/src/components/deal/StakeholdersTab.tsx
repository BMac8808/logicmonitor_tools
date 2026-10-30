import { useState } from "react";
import { api } from "../../api";
import type { Influence, Stakeholder, Stance } from "../../types";
import { attempt, Badge, Empty, ErrorBanner, StatusBadge, useAsync, useLibrary } from "../../ui";

const blank = { name: "", title: "", persona_id: "", influence: "medium" as Influence, stance: "unknown" as Stance, notes: "" };

export default function StakeholdersTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const lib = useLibrary();
  const list = useAsync(() => api.stakeholders(dealId), [dealId]);
  const [form, setForm] = useState({ ...blank, persona_id: lib.personaList[0]?.id ?? "" });
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await attempt(() => api.addStakeholder(dealId, form), setError)) {
      setForm({ ...blank, persona_id: form.persona_id });
      await list.reload();
      onChange();
    }
  };
  const update = async (s: Stakeholder, patch: Partial<Stakeholder>) => {
    if (await attempt(() => api.updateStakeholder(s.id, patch), setError)) {
      await list.reload();
      onChange();
    }
  };
  const remove = async (s: Stakeholder) => {
    if (!window.confirm(`Remove ${s.name}?`)) return;
    if (await attempt(() => api.deleteStakeholder(s.id), setError)) {
      await list.reload();
      onChange();
    }
  };

  const present = new Set(list.data?.map((s) => s.persona_id));
  const missingRequired = lib.personaList.filter((p) => p.coverage === "required" && !present.has(p.id));

  return (
    <div>
      <ErrorBanner error={error ?? list.error} onDismiss={() => setError(null)} />
      {list.data && missingRequired.length > 0 && (
        <div className="banner banner-warn">
          Not yet identified: {missingRequired.map((p) => p.name).join(", ")}.
        </div>
      )}
      <form className="card" onSubmit={add} aria-label="Add stakeholder">
        <h2>Add stakeholder</h2>
        <div className="form-grid">
          <label>Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Title<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>
            Persona
            <select value={form.persona_id} onChange={(e) => setForm({ ...form, persona_id: e.target.value })}>
              {lib.personaList.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>
            Influence
            <select value={form.influence} onChange={(e) => setForm({ ...form, influence: e.target.value as Influence })}>
              <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
          </label>
          <label>
            Stance
            <select value={form.stance} onChange={(e) => setForm({ ...form, stance: e.target.value as Stance })}>
              <option value="supporter">Supporter</option><option value="neutral">Neutral</option>
              <option value="skeptic">Skeptic</option><option value="unknown">Unknown</option>
            </select>
          </label>
          <label className="full">Notes<input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
        </div>
        {lib.personas[form.persona_id] && <p className="muted small" style={{ marginTop: 8 }}>{lib.personas[form.persona_id].summary}</p>}
        <button type="submit">Add stakeholder</button>
      </form>
      <div className="card">
        <h2>Stakeholders</h2>
        {!list.data?.length ? (
          <Empty>No stakeholders yet. Discovery questions are tailored to the personas you add.</Empty>
        ) : (
          <table>
            <thead><tr><th>Name</th><th>Persona</th><th>Influence</th><th>Stance</th><th></th></tr></thead>
            <tbody>
              {list.data.map((s) => {
                const persona = lib.personas[s.persona_id];
                return (
                  <tr key={s.id}>
                    <td>
                      <strong>{s.name}</strong>
                      <div className="muted small">{s.title}</div>
                      {s.notes && <div className="small">{s.notes}</div>}
                      {expanded === s.id && persona && (
                        <div className="small" style={{ marginTop: 8 }}>
                          <h4>Engagement approach</h4>
                          <ul>{persona.engagement_approach.map((x) => <li key={x}>{x}</li>)}</ul>
                          <h4>Typical objections</h4>
                          <ul>{persona.typical_objections.map((o) => <li key={o.objection}><em>{o.objection}</em> — {o.approach}</li>)}</ul>
                          <h4>Signals</h4>
                          <ul>{persona.discovery_signals.map((x) => <li key={x}>{x}</li>)}</ul>
                        </div>
                      )}
                    </td>
                    <td>
                      <select aria-label={`Persona for ${s.name}`} value={s.persona_id} onChange={(e) => update(s, { persona_id: e.target.value })}>
                        {lib.personaList.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                      <div>
                        <button type="button" className="link small" onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
                          {expanded === s.id ? "Hide guidance" : "Show guidance"}
                        </button>
                      </div>
                    </td>
                    <td><StatusBadge value={s.influence} /></td>
                    <td><Badge tone={s.stance === "supporter" ? "good" : s.stance === "skeptic" ? "bad" : "neutral"}>{s.stance}</Badge></td>
                    <td><button type="button" className="danger" onClick={() => remove(s)}>Remove</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
