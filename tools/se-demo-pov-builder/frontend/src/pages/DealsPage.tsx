import { useState } from "react";
import { api } from "../api";
import { navigate } from "../router";
import ContextChips from "../components/ContextChips";
import { attempt, Empty, ErrorBanner, StatusBadge, useAsync } from "../ui";

function NewDealForm({ onCreated }: { onCreated: (dealId: number) => void }) {
  const accounts = useAsync(() => api.accounts(), []);
  const [accountId, setAccountId] = useState<string>("new");
  const [accountName, setAccountName] = useState("");
  const [industry, setIndustry] = useState("");
  const [region, setRegion] = useState("");
  const [fictional, setFictional] = useState(false);
  const [dealName, setDealName] = useState("");
  const [summary, setSummary] = useState("");
  const [context, setContext] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    await attempt(async () => {
      let id = Number(accountId);
      if (accountId === "new") {
        id = (await api.createAccount({ name: accountName, industry, region, is_synthetic: fictional })).id;
      }
      const deal = await api.createDeal({ account_id: id, name: dealName, summary, technical_context: context });
      onCreated(deal.id);
    }, setError);
    setBusy(false);
  };

  return (
    <form className="card" onSubmit={submit} aria-label="Create deal">
      <h2>New deal</h2>
      <p className="muted small">
        Real customer data stays on this machine. Mark fictional accounts as such, so exports and LMDA show which is which.
      </p>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <div className="form-grid">
        <label>
          Account
          <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
            <option value="new">+ New account</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </label>
        {accountId === "new" && (
          <>
            <label>
              Account name
              <input required value={accountName} onChange={(e) => setAccountName(e.target.value)} />
            </label>
            <label>
              Industry
              <input value={industry} onChange={(e) => setIndustry(e.target.value)} />
            </label>
            <label>
              Region
              <input value={region} onChange={(e) => setRegion(e.target.value)} />
            </label>
            <label className="inline full">
              <input type="checkbox" checked={fictional} onChange={(e) => setFictional(e.target.checked)} />
              Fictional or sample account (not a real customer)
            </label>
          </>
        )}
        <label>
          Deal name
          <input required value={dealName} onChange={(e) => setDealName(e.target.value)} />
        </label>
        <label className="full">
          Summary
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <div className="full">
          <div className="muted small" style={{ marginBottom: 4 }}>Technologies in scope (drives discovery questions)</div>
          <ContextChips value={context} onChange={setContext} />
        </div>
      </div>
      <div className="row" style={{ marginTop: "0.8rem" }}>
        <button type="submit" disabled={busy}>Create deal</button>
      </div>
    </form>
  );
}

export default function DealsPage({ allowSample }: { allowSample: boolean }) {
  const deals = useAsync(() => api.deals(), []);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSample = () =>
    attempt(async () => {
      const r = await api.loadSample();
      navigate(`/deals/${r.deal_id}/overview`);
    }, setError);

  return (
    <div>
      <div className="row spread" style={{ marginBottom: "1rem" }}>
        <h1>Deals</h1>
        <div className="row">
          {allowSample && (
            <button type="button" className="secondary" onClick={loadSample}>Load sample engagement</button>
          )}
          <button type="button" onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New deal"}</button>
        </div>
      </div>
      <ErrorBanner error={error ?? deals.error} onDismiss={() => setError(null)} />
      {showForm && <NewDealForm onCreated={(id) => navigate(`/deals/${id}/stakeholders`)} />}
      <div className="card">
        {deals.loading && !deals.data ? (
          <p className="muted">Loading…</p>
        ) : !deals.data?.length ? (
          <Empty>No deals yet. Create one, or load the synthetic sample engagement to explore the full workflow.</Empty>
        ) : (
          <table>
            <thead>
              <tr><th>Deal</th><th>Account</th><th>Stage</th><th>Context</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {deals.data.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/deals/${d.id}/overview`}>{d.name}</a></td>
                  <td>{d.account_name}</td>
                  <td><StatusBadge value={d.stage} /></td>
                  <td className="small muted">{d.technical_context.join(", ") || "—"}</td>
                  <td className="small muted">{new Date(d.updated_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
