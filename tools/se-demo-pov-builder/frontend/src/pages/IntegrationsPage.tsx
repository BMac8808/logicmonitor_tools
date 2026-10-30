import { useState } from "react";
import { api, getToken, setToken } from "../api";
import type { Adapter, AdapterAction, AdapterResult } from "../types";
import { attempt, Badge, ErrorBanner, useAsync } from "../ui";

function ActionRunner({ adapter, action }: { adapter: Adapter; action: AdapterAction }) {
  const [params, setParams] = useState<Record<string, string>>({});
  const [approver, setApprover] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<AdapterResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const writes = action.kind === "state_changing";

  const run = () =>
    attempt(async () => {
      const cleaned = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== ""));
      const authorization = writes && approver && reason ? {
        approved_by: approver, reason, scope: [`${adapter.id}:${action.name}`],
        expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      } : undefined;
      setResult(await api.runAdapterAction(adapter.id, action.name, { params: cleaned, authorization }));
    }, (e) => { setError(e); if (e) setResult(null); });

  return (
    <div className="question">
      <div className="row spread">
        <div>
          <code>{action.name}</code> <Badge tone={writes ? "warn" : "info"}>{writes ? "state-changing" : "read-only"}</Badge>
          <div className="muted small">{action.description}</div>
        </div>
        <button type="button" className="secondary" onClick={run}>{writes ? "Dry run (mock)" : "Run (mock)"}</button>
      </div>
      {(action.params.length > 0 || writes) && (
        <div className="row" style={{ marginTop: 6 }}>
          {action.params.filter((p) => p.type === "string").map((p) => (
            <input key={p.name} aria-label={p.name} placeholder={`${p.name}${p.required ? " *" : ""}`}
              value={params[p.name] ?? ""} onChange={(e) => setParams({ ...params, [p.name]: e.target.value })} />
          ))}
          {writes && (
            <>
              <input aria-label="Approved by" placeholder="Approved by *" value={approver} onChange={(e) => setApprover(e.target.value)} />
              <input aria-label="Reason" placeholder="Reason *" value={reason} onChange={(e) => setReason(e.target.value)} />
            </>
          )}
        </div>
      )}
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {result && (
        <>
          <div className="banner banner-sim small" style={{ marginTop: 6 }}>SIMULATED — {result.message}</div>
          <pre className="output">{JSON.stringify(result.data, null, 2)}</pre>
        </>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  const adapters = useAsync(() => api.adapters(), []);
  const [token, setTokenValue] = useState(getToken());
  const [saved, setSaved] = useState(false);

  return (
    <div>
      <h1>Integrations</h1>
      <div className="banner banner-warn">
        All adapters are mocks returning synthetic data. Nothing here contacts a real system. Live integrations will be
        added only after verification against official documentation. State-changing actions always require an explicit
        authorization and, in mock mode, only describe what they would do.
      </div>
      <ErrorBanner error={adapters.error} />
      {adapters.data?.map((a) => (
        <div key={a.id} className="card">
          <div className="row spread">
            <h2>{a.name}</h2>
            <div className="row"><Badge tone="sim">{a.mode}</Badge>{!a.verified && <Badge tone="warn">unverified</Badge>}</div>
          </div>
          <p className="small">{a.description} <span className="muted">{a.notes}</span></p>
          {a.actions.map((act) => <ActionRunner key={act.name} adapter={a} action={act} />)}
        </div>
      ))}
      <form className="card narrow" onSubmit={(e) => { e.preventDefault(); setToken(token.trim()); setSaved(true); }}>
        <h2>API token (optional)</h2>
        <p className="small muted">Only needed when the server sets <code>SEPB_API_TOKEN</code>. Stored in this browser.</p>
        <input type="password" aria-label="API token" value={token} onChange={(e) => { setTokenValue(e.target.value); setSaved(false); }} autoComplete="off" />
        <div className="row" style={{ marginTop: 8 }}><button type="submit">Save</button>{saved && <span className="muted small">Saved</span>}</div>
      </form>
    </div>
  );
}
