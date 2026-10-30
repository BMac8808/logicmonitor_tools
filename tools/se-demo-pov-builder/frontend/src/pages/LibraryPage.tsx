import { useState } from "react";
import { api } from "../api";
import { attempt, Badge, ErrorBanner, useAsync, useLibrary } from "../ui";

type Section = "personas" | "capabilities" | "scenarios" | "workflows";

export default function LibraryPage({ onReloaded }: { onReloaded: () => void }) {
  const lib = useLibrary();
  const scenarios = useAsync(() => api.scenarios(), []);
  const workflows = useAsync(() => api.workflows(), []);
  const [section, setSection] = useState<Section>("personas");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const reload = () =>
    attempt(async () => {
      const r = await api.reloadContent();
      setMessage(`Reloaded: ${Object.entries(r).map(([k, v]) => `${v} ${k}`).join(", ")}`);
      onReloaded();
      void scenarios.reload();
      void workflows.reload();
    }, setError);

  return (
    <div>
      <div className="row spread" style={{ marginBottom: "1rem" }}>
        <h1>Content library</h1>
        <button type="button" className="secondary" onClick={reload}>Reload content from disk</button>
      </div>
      <p className="muted">
        Everything here is loaded from YAML files in <code>personas/</code>, <code>knowledge/</code> and{" "}
        <code>workflows/</code>. Edit those files and reload; no code changes needed.
      </p>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {message && <div className="banner banner-info">{message}</div>}
      <nav className="tabs">
        {(["personas", "capabilities", "scenarios", "workflows"] as Section[]).map((s) => (
          <a key={s} href="#/library" className={section === s ? "active" : undefined}
            onClick={(e) => { e.preventDefault(); setSection(s); }}>
            {s[0].toUpperCase() + s.slice(1)}
          </a>
        ))}
      </nav>

      {section === "personas" && (
        <div className="grid grid-2">
          {lib.personaList.map((p) => (
            <div key={p.id} className="card">
              <div className="row spread">
                <h2>{p.name}</h2>
                <div className="row"><Badge tone={p.coverage === "required" ? "bad" : "neutral"}>{p.coverage}</Badge><Badge>{p.typical_influence} influence</Badge></div>
              </div>
              <p>{p.summary}</p>
              <details><summary>Objectives &amp; motivations</summary>
                <ul>{[...p.objectives, ...p.motivations].map((x) => <li key={x}>{x}</li>)}</ul>
              </details>
              <details><summary>Technical concerns</summary><ul>{p.technical_concerns.map((x) => <li key={x}>{x}</li>)}</ul></details>
              <details><summary>Typical objections</summary>
                <ul>{p.typical_objections.map((o) => <li key={o.objection}><em>{o.objection}</em> — {o.approach}</li>)}</ul>
              </details>
              <details><summary>Discovery signals</summary><ul>{p.discovery_signals.map((x) => <li key={x}>{x}</li>)}</ul></details>
              <details><summary>Engagement approach</summary>
                <p className="small">{p.influence_notes}</p>
                <ul>{p.engagement_approach.map((x) => <li key={x}>{x}</li>)}</ul>
              </details>
            </div>
          ))}
        </div>
      )}

      {section === "capabilities" && (
        <div className="card">
          <div className="banner banner-warn">{lib.capabilities.disclaimer}</div>
          <table>
            <thead><tr><th>Capability</th><th>Category</th><th>Description</th><th>Verified</th></tr></thead>
            <tbody>
              {lib.capabilities.capabilities.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong><div className="muted small"><code>{c.id}</code></div></td>
                  <td>{c.category}</td>
                  <td className="small">{c.description}<div className="muted">Keywords: {c.keywords.join(", ")}</div></td>
                  <td>{c.verified ? <Badge tone="good">verified</Badge> : <Badge tone="warn">unverified</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {section === "scenarios" && (
        <div className="grid grid-2">
          {scenarios.data?.map((s) => (
            <div key={s.id} className="card">
              <h3>{s.title} <span className="muted small">· {s.duration_minutes} min</span></h3>
              <p>{s.summary}</p>
              <ul className="small">{s.demonstrates.map((d) => <li key={d}>{d}</li>)}</ul>
              <div className="chips">{s.capabilities.map((c) => <Badge key={c}>{lib.capabilityName(c)}</Badge>)}</div>
            </div>
          ))}
        </div>
      )}

      {section === "workflows" && (
        <div className="grid grid-2">
          {workflows.data?.map((w) => (
            <div key={w.id} className="card">
              <h3>{w.name} <span className="muted small">v{w.version}</span></h3>
              <p className="small">{w.description}</p>
              {w.stages.map((s) => (
                <div key={s.id} className="small">
                  <strong>{s.name}</strong>
                  <ul>{s.tasks.map((t) => <li key={t.key}>{t.title}</li>)}</ul>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
