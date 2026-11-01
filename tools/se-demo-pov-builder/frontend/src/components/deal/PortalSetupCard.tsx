import { useState } from "react";
import { api } from "../../api";
import type { PovPlan, ReadinessCheck, ReadinessResult } from "../../types";
import { attempt, Badge, downloadText, ErrorBanner, slug, useLibrary } from "../../ui";

const CHECK_TONES: Record<ReadinessCheck["status"], string> = { ok: "good", warn: "warn", fail: "bad", error: "bad" };

function AttachEvidence({ check, result, plan, onAttached }: {
  check: ReadinessCheck; result: ReadinessResult; plan: PovPlan; onAttached: () => void;
}) {
  const [criterionId, setCriterionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  if (!plan.criteria.length) return null;
  if (done) return <span className="muted small">Attached ✓</span>;
  const attach = () =>
    attempt(async () => {
      await api.addEvidence(Number(criterionId), {
        description: `${check.title}: ${check.detail}`,
        reference: `${result.source}; ${check.calls.map((c) => `${c.tool} ${JSON.stringify(c.arguments)}`).join("; ")}; ${result.checked_at}`,
        evidence_type: "observation",
        is_simulated: result.simulated,
        recorded_by: "Readiness check",
      });
      setDone(true);
      onAttached();
    }, setError);
  return (
    <div className="row">
      <select aria-label={`Criterion for ${check.title}`} value={criterionId} onChange={(e) => setCriterionId(e.target.value)}>
        <option value="">Attach to criterion…</option>
        {plan.criteria.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
      </select>
      <button type="button" className="secondary" disabled={!criterionId} onClick={attach}>Attach</button>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
    </div>
  );
}

export default function PortalSetupCard({ plan, reload }: { plan: PovPlan; reload: () => void }) {
  const { ecosystem } = useLibrary();
  const [group, setGroup] = useState(plan.portal_group ?? "");
  const [selected, setSelected] = useState<string[]>([]);
  const [subgroups, setSubgroups] = useState(true);
  const [result, setResult] = useState<ReadinessResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const milestoneTitles = Object.fromEntries(plan.milestones.map((m) => [m.template_key, m.title]));
  const psModule = ecosystem.projects.find((p) => p.id === "lm_powershell_module");
  const mcp = ecosystem.projects.find((p) => p.id === "logicmonitor_api_mcp");

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const runCheck = async () => {
    setBusy(true);
    await attempt(async () => setResult(await api.povReadiness(plan.id)), setError);
    setBusy(false);
  };
  const download = () =>
    attempt(async () => {
      const text = await api.povSetupScript(plan.id, { toolkit_ids: selected, include_subgroups: subgroups });
      downloadText(`pov-setup-${slug(plan.portal_group ?? plan.title)}.ps1`, text, "text/plain");
    }, setError);

  return (
    <div className="card">
      <h2>LogicMonitor portal setup</h2>
      <p className="muted small">
        This app plans; portal work is done by public LogicMonitor tooling. Readiness checks read through the{" "}
        <a href={mcp?.docs} target="_blank" rel="noreferrer">logicmonitor-api-mcp</a> server (read-only). Changes are made by a
        generated <a href={psModule?.docs} target="_blank" rel="noreferrer">Logic.Monitor</a> PowerShell script that you review
        and run yourself. This app never stores LogicMonitor credentials.
      </p>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <form className="row" onSubmit={(e) => {
        e.preventDefault();
        void attempt(() => api.updatePovPlan(plan.id, { portal_group: group.trim() }), setError).then((ok) => ok && reload());
      }}>
        <label className="inline">Portal resource group
          <input value={group} onChange={(e) => setGroup(e.target.value)} style={{ minWidth: 320 }} />
        </label>
        <button type="submit" className="secondary" disabled={!group.trim() || group === plan.portal_group}>Save</button>
      </form>

      <h3 style={{ marginTop: 16 }}>Readiness check (read-only)</h3>
      <button type="button" onClick={runCheck} disabled={busy}>{busy ? "Checking…" : "Run readiness check"}</button>
      {result && (
        <div style={{ marginTop: 8 }}>
          {result.simulated ? (
            <div className="banner banner-sim small">SIMULATED — mock fixtures, not the customer's portal. Configure SEPB_ADAPTER_MODE=mcp for real reads.</div>
          ) : (
            <div className="banner banner-info small">Read from the customer's portal via {result.source} at {new Date(result.checked_at).toLocaleString()}.</div>
          )}
          <table>
            <tbody>
              {result.checks.map((c) => (
                <tr key={c.id}>
                  <td style={{ width: 70 }}><Badge tone={CHECK_TONES[c.status]}>{c.status}</Badge></td>
                  <td>
                    <strong>{c.title}</strong>
                    <div className="small">{c.detail}</div>
                    <div className="muted small">{[...new Set(c.calls.map((call) => call.tool))].join(", ")}</div>
                  </td>
                  <td style={{ width: 280 }}>
                    {c.status !== "error" && <AttachEvidence check={c} result={result} plan={plan} onAttached={reload} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ marginTop: 16 }}>Setup script (Logic.Monitor PowerShell)</h3>
      <p className="muted small">
        Creates the POV resource group (and one subgroup per technology in scope) and imports the toolkit LogicModules you
        select from their public repositories at pinned commits. Existing modules are never overwritten. Runs as a dry run
        unless started with <code>-Apply</code>.
      </p>
      <table>
        <thead><tr><th></th><th>Toolkit item</th><th>Used for</th><th>Import</th></tr></thead>
        <tbody>
          {ecosystem.toolkit.map((t) => (
            <tr key={t.id}>
              <td><input type="checkbox" aria-label={`Include ${t.title}`} checked={selected.includes(t.id)} onChange={() => toggle(t.id)} /></td>
              <td>
                <a href={t.source_url} target="_blank" rel="noreferrer">{t.title}</a> <span className="muted small">({t.kind}, {t.license})</span>
                <div className="small">{t.purpose}</div>
                {t.requires.length > 0 && <div className="muted small">Also includes: {t.requires.join(", ")}</div>}
              </td>
              <td className="small">{t.milestones.map((m) => milestoneTitles[m] ?? m).join("; ")}</td>
              <td>{t.import === "powershell" ? <Badge tone="outline">script</Badge> : <Badge tone="outline">manual</Badge>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row" style={{ marginTop: 8 }}>
        <label className="inline small">
          <input type="checkbox" checked={subgroups} onChange={(e) => setSubgroups(e.target.checked)} />
          Create a subgroup per technology in scope
        </label>
        <button type="button" onClick={download}>Download setup script (.ps1)</button>
      </div>
      {psModule && <p className="muted small" style={{ marginTop: 6 }}>Requires: <code>{psModule.install}</code></p>}
    </div>
  );
}
