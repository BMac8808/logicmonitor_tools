import { api } from "../api";
import { useState } from "react";
import { attempt, downloadText, ErrorBanner, slug, useAsync } from "../ui";
import OverviewTab from "../components/deal/OverviewTab";
import StakeholdersTab from "../components/deal/StakeholdersTab";
import DiscoveryTab from "../components/deal/DiscoveryTab";
import RequirementsTab from "../components/deal/RequirementsTab";
import DemoPlanTab from "../components/deal/DemoPlanTab";
import PovTab from "../components/deal/PovTab";
import WorkflowsTab from "../components/deal/WorkflowsTab";
import NextActionsTab from "../components/deal/NextActionsTab";
import type { DealDetail } from "../types";

const TABS: { id: string; label: string; count?: (d: DealDetail) => string }[] = [
  { id: "overview", label: "Overview" },
  { id: "stakeholders", label: "Stakeholders", count: (d) => `${d.metrics.stakeholders}` },
  { id: "discovery", label: "Discovery", count: (d) => `${d.metrics.questions_answered}/${d.metrics.questions_total}` },
  { id: "requirements", label: "Requirements", count: (d) => `${d.metrics.requirements}` },
  { id: "demo", label: "Demo plan", count: (d) => `${d.metrics.demo_plans}` },
  { id: "pov", label: "POV", count: (d) => `${d.metrics.criteria_met}/${d.metrics.criteria_total}` },
  { id: "workflows", label: "Workflows" },
  { id: "actions", label: "Next actions", count: (d) => `${d.metrics.open_next_actions}` },
];

export default function DealWorkspace({ dealId, tab, llmEnabled }: { dealId: number; tab: string; llmEnabled: boolean }) {
  const deal = useAsync(() => api.deal(dealId), [dealId]);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const refresh = () => void deal.reload();
  const d = deal.data;
  const handoffJson = async () => JSON.stringify(await api.handoff(dealId), null, 2);
  const toggleFictional = (fictional: boolean) => {
    const msg = fictional
      ? "Mark this account as fictional? Exports and LMDA will label its data as synthetic."
      : "Mark this account as real customer data? Exports and LMDA will label it as customer data.";
    if (!window.confirm(msg) || !d) return;
    void attempt(async () => { await api.updateAccount(d.account.id, { is_synthetic: fictional }); refresh(); }, setError);
  };
  // LMDA's import dialog takes pasted JSON, so copying saves opening the downloaded file.
  const copyHandoff = () => attempt(async () => {
    const text = await handoffJson();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      throw new Error("The browser blocked copying to the clipboard. Use Export LMDA handoff (JSON) and copy from the file.");
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, setError);

  if (deal.error) return <ErrorBanner error={deal.error} />;
  if (!d) return <p className="muted">Loading…</p>;

  return (
    <div>
      <div className="row spread">
        <div>
          <div className="muted small"><a href="#/">Deals</a> / {d.account.name}</div>
          <h1>{d.name}</h1>
          <div className="row small" aria-label="Data classification">
            {d.account.is_synthetic
              ? <span className="badge badge-outline">Fictional data</span>
              : <span className="badge badge-outline-strong">Customer data</span>}
            <button type="button" className="link small" onClick={() => toggleFictional(!d.account.is_synthetic)}>
              {d.account.is_synthetic ? "Mark as real customer" : "Mark as fictional"}
            </button>
          </div>
        </div>
        <div className="row">
        {d.external_system && (
          <span className="small muted">
            Linked to {d.external_system.toUpperCase()}{" "}
            {d.external_url ? <a href={d.external_url} target="_blank" rel="noreferrer">{d.external_id}</a> : d.external_id}
          </span>
        )}
        {d.external_import_link && (
          <a className="button-link" href={d.external_import_link} target="_blank" rel="noreferrer"
            title="Opens the LMDA Scoping Doc with this deal ready to import">
            Send to LMDA
          </a>
        )}
        <button type="button" className="secondary" title="Versioned JSON package for downstream SE platforms such as LMDA"
          onClick={() => attempt(async () => downloadText(`handoff-${slug(d.name)}.json`, await handoffJson(),
            "application/json"), setError)}>
          Export LMDA handoff (JSON)
        </button>
        <button type="button" className="secondary" title="Copies the same JSON, ready to paste into LMDA's Paste handoff JSON tab"
          onClick={copyHandoff}>
          {copied ? "Copied" : "Copy handoff JSON"}
        </button>
        </div>
      </div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <nav className="tabs" aria-label="Deal sections">
        {TABS.map((t) => (
          <a key={t.id} href={`#/deals/${dealId}/${t.id}`} className={tab === t.id ? "active" : undefined}>
            {t.label}
            {t.count && <span className="count">{t.count(d)}</span>}
          </a>
        ))}
      </nav>
      {tab === "overview" && <OverviewTab deal={d} onChange={refresh} />}
      {tab === "stakeholders" && <StakeholdersTab dealId={dealId} onChange={refresh} />}
      {tab === "discovery" && <DiscoveryTab dealId={dealId} onChange={refresh} llmEnabled={llmEnabled} />}
      {tab === "requirements" && <RequirementsTab dealId={dealId} onChange={refresh} />}
      {tab === "demo" && <DemoPlanTab dealId={dealId} onChange={refresh} />}
      {tab === "pov" && <PovTab dealId={dealId} onChange={refresh} />}
      {tab === "workflows" && <WorkflowsTab dealId={dealId} onChange={refresh} />}
      {tab === "actions" && <NextActionsTab dealId={dealId} onChange={refresh} />}
    </div>
  );
}
