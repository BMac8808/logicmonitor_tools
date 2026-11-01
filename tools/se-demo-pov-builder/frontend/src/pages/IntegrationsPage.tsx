import { useState } from "react";
import { api, getToken, setToken } from "../api";
import type { Adapter, AdapterAction, AdapterResult } from "../types";
import { attempt, Badge, ErrorBanner, useAsync, useLibrary } from "../ui";

function ActionRunner({ adapter, action }: { adapter: Adapter; action: AdapterAction & { mcp_tool?: string } }) {
  const [filter, setFilter] = useState("");
  const [size, setSize] = useState("10");
  const [result, setResult] = useState<AdapterResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = () =>
    attempt(async () => {
      const params: Record<string, unknown> = { size: Number(size) || 10 };
      if (filter.trim()) params.filter = filter.trim();
      setResult(await api.runAdapterAction(adapter.id, action.name, { params }));
    }, (e) => { setError(e); if (e) setResult(null); });

  return (
    <div className="question">
      <div className="row spread">
        <div>
          <code>{action.name}</code> <Badge tone="outline">read-only</Badge>{" "}
          {action.mcp_tool && <span className="muted small">MCP tool <code>{action.mcp_tool}</code></span>}
          <div className="muted small">{action.description}</div>
        </div>
        <div className="row">
          <input aria-label={`Filter for ${action.name}`} placeholder='Filter, e.g. isDown:true' value={filter} onChange={(e) => setFilter(e.target.value)} />
          <input aria-label={`Size for ${action.name}`} type="number" min={1} max={1000} value={size} onChange={(e) => setSize(e.target.value)} style={{ width: 70 }} />
          <button type="button" className="secondary" onClick={run}>Run</button>
        </div>
      </div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {result && (
        <>
          <div className={`banner small ${result.simulated ? "banner-sim" : "banner-info"}`} style={{ marginTop: 6 }}>
            {result.simulated ? "SIMULATED — " : ""}{result.message}
          </div>
          <pre className="output">{JSON.stringify(result.data, null, 2)}</pre>
        </>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  const { ecosystem } = useLibrary();
  const adapters = useAsync(() => api.adapters(), []);
  const [token, setTokenValue] = useState(getToken());
  const [saved, setSaved] = useState(false);
  const mcp = ecosystem.projects.find((p) => p.id === "logicmonitor_api_mcp");
  const ps = ecosystem.projects.find((p) => p.id === "lm_powershell_module");

  return (
    <div>
      <h1>Integrations</h1>
      <p>
        This app plans engagements. Anything that touches a LogicMonitor portal reuses public community tooling instead of
        a home-grown API client:
      </p>
      <ul>
        <li><strong>Reads</strong> go through the <a href={mcp?.docs} target="_blank" rel="noreferrer">{mcp?.name}</a> ({mcp?.license}), which you run yourself and which holds the portal credentials.</li>
        <li><strong>Changes</strong> are generated as <a href={ps?.docs} target="_blank" rel="noreferrer">{ps?.name}</a> ({ps?.license}) scripts on the POV tab, for a person to review and run.</li>
      </ul>
      <ErrorBanner error={adapters.error} />
      {adapters.data?.map((a) => (
        <div key={a.id} className="card">
          <div className="row spread">
            <h2>{a.name}</h2>
            <div className="row">
              <Badge tone={a.mode === "mock" ? "sim" : "good"}>{a.mode === "mock" ? "mock (synthetic)" : "live via MCP"}</Badge>
            </div>
          </div>
          <p className="small">{a.description} <span className="muted">{a.notes}</span></p>
          {a.mode === "mock" && (
            <details>
              <summary>Connect to a real portal (read-only)</summary>
              <ol className="small">
                <li>Start the MCP server on your machine (credentials stay in its environment):
                  <pre className="output">{mcp?.install}</pre></li>
                <li>Optionally set <code>AUTH_MODE=bearer</code> and <code>MCP_BEARER_TOKENS</code> on the server, and the same token in <code>SEPB_MCP_TOKEN</code>.</li>
                <li>Restart this app with <code>SEPB_ADAPTER_MODE=mcp</code> and <code>SEPB_MCP_URL=http://127.0.0.1:3000/mcp</code>.</li>
              </ol>
            </details>
          )}
          {a.actions.map((act) => <ActionRunner key={act.name} adapter={a} action={act} />)}
        </div>
      ))}
      <form className="card narrow" onSubmit={(e) => { e.preventDefault(); setToken(token.trim()); setSaved(true); }}>
        <h2>API token (optional)</h2>
        <p className="small muted">Only needed when this app's server sets <code>SEPB_API_TOKEN</code>. Stored in this browser.</p>
        <input type="password" aria-label="API token" value={token} onChange={(e) => { setTokenValue(e.target.value); setSaved(false); }} autoComplete="off" />
        <div className="row" style={{ marginTop: 8 }}><button type="submit">Save</button>{saved && <span className="muted small">Saved</span>}</div>
      </form>
    </div>
  );
}
