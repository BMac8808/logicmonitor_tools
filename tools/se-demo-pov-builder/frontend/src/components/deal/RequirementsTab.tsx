import { useState } from "react";
import { api } from "../../api";
import type { CapabilityMatch, Priority, Requirement } from "../../types";
import { attempt, Badge, Empty, ErrorBanner, StatusBadge, useAsync, useLibrary } from "../../ui";

function CapabilityPicker({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const lib = useLibrary();
  return (
    <select multiple aria-label="Capabilities" value={value} style={{ minHeight: 120, width: "100%" }}
      onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}>
      {lib.capabilities.capabilities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
    </select>
  );
}

export default function RequirementsTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const lib = useLibrary();
  const reqs = useAsync(() => api.requirements(dealId), [dealId]);
  const [form, setForm] = useState({ title: "", description: "", pain_point: "", priority: "should" as Priority, category: "technical" as "technical" | "business" });
  const [caps, setCaps] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<CapabilityMatch[] | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [editCaps, setEditCaps] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const suggest = () =>
    attempt(async () => {
      const m = await api.matchCapabilities(`${form.title} ${form.description} ${form.pain_point}`);
      setSuggestions(m);
      setCaps(m.slice(0, 4).map((x) => x.capability_id));
    }, setError);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await attempt(() => api.createRequirement(dealId, { ...form, capability_ids: caps }), setError)) {
      setForm({ ...form, title: "", description: "", pain_point: "" });
      setCaps([]);
      setSuggestions(null);
      await reqs.reload();
      onChange();
    }
  };

  const update = async (r: Requirement, patch: Partial<Requirement>) => {
    if (await attempt(() => api.updateRequirement(r.id, patch), setError)) {
      await reqs.reload();
      onChange();
    }
  };

  const remove = async (r: Requirement) => {
    if (!window.confirm(`Delete requirement "${r.title}"?`)) return;
    if (await attempt(() => api.deleteRequirement(r.id), setError)) {
      await reqs.reload();
      onChange();
    }
  };

  return (
    <div>
      <ErrorBanner error={error ?? reqs.error} onDismiss={() => setError(null)} />
      <div className="banner banner-info small">{lib.capabilities.disclaimer}</div>
      <form className="card" onSubmit={add} aria-label="Add requirement">
        <h2>Add requirement</h2>
        <p className="muted small">Tip: create requirements directly from saved answers on the Discovery tab to keep their source.</p>
        <div className="form-grid">
          <label className="full">Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>
            Priority
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}>
              <option value="must">Must</option><option value="should">Should</option><option value="could">Could</option>
            </select>
          </label>
          <label>
            Category
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as "technical" | "business" })}>
              <option value="technical">Technical</option><option value="business">Business</option>
            </select>
          </label>
          <label className="full">Pain point (customer's words)<textarea value={form.pain_point} onChange={(e) => setForm({ ...form, pain_point: e.target.value })} /></label>
          <label className="full">Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <div className="full">
            <div className="row spread">
              <span className="muted small">Mapped capabilities</span>
              <button type="button" className="secondary" onClick={suggest} disabled={!form.title.trim()}>Suggest from text</button>
            </div>
            {suggestions && (
              <p className="small muted">
                {suggestions.length ? suggestions.slice(0, 6).map((s) => `${s.name} (${s.matched_keywords.join(", ") || "from question"})`).join(" · ") : "No keyword matches."}
              </p>
            )}
            <CapabilityPicker value={caps} onChange={setCaps} />
          </div>
        </div>
        <button type="submit" style={{ marginTop: 8 }}>Add requirement</button>
      </form>
      <div className="card">
        <h2>Requirements</h2>
        {!reqs.data?.length ? (
          <Empty>No requirements yet.</Empty>
        ) : (
          <table>
            <thead><tr><th>Requirement</th><th>Priority</th><th>Capabilities</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {reqs.data.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.title}</strong>
                    {r.pain_point && <div className="small">Pain: {r.pain_point}</div>}
                    {r.source_question_id && <div className="muted small">From discovery: <code>{r.source_question_id}</code></div>}
                    {(() => {
                      const refs = lib.ecosystem.references.filter((ref) => ref.capabilities.some((c) => r.capability_ids.includes(c)));
                      return refs.length > 0 && (
                        <div className="small">Related public tooling:{" "}
                          {refs.map((ref, i) => (
                            <span key={ref.id}>{i > 0 && " · "}<a href={ref.source_url} target="_blank" rel="noreferrer">{ref.title}</a></span>
                          ))}
                        </div>
                      );
                    })()}
                  </td>
                  <td>
                    <select aria-label={`Priority for ${r.title}`} value={r.priority} onChange={(e) => update(r, { priority: e.target.value as Priority })}>
                      <option value="must">must</option><option value="should">should</option><option value="could">could</option>
                    </select>
                  </td>
                  <td style={{ minWidth: 220 }}>
                    {editing === r.id ? (
                      <div className="stack">
                        <CapabilityPicker value={editCaps} onChange={setEditCaps} />
                        <div className="row">
                          <button type="button" onClick={async () => { await update(r, { capability_ids: editCaps }); setEditing(null); }}>Save</button>
                          <button type="button" className="secondary" onClick={() => setEditing(null)}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="chips">
                          {r.capability_ids.length ? r.capability_ids.map((c) => <Badge key={c}>{lib.capabilityName(c)}</Badge>) : <StatusBadge value="missing" />}
                        </div>
                        <button type="button" className="link small" onClick={() => { setEditing(r.id); setEditCaps(r.capability_ids); }}>Edit mapping</button>
                      </>
                    )}
                  </td>
                  <td>
                    <select aria-label={`Status for ${r.title}`} value={r.status} onChange={(e) => update(r, { status: e.target.value as "draft" | "confirmed" })}>
                      <option value="draft">draft</option><option value="confirmed">confirmed</option>
                    </select>
                  </td>
                  <td><button type="button" className="danger" onClick={() => remove(r)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
