import { useState } from "react";
import { api } from "../../api";
import type { DealDetail } from "../../types";
import ContextChips from "../ContextChips";
import GapsList from "./GapsList";
import { attempt, ErrorBanner, useAsync } from "../../ui";

const STAGES = ["discovery", "technical_qualification", "demo_preparation", "pov_planning", "pov_execution",
  "success_validation", "technical_handoff", "closed_won", "closed_lost"];

function Metric({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="metric">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

export default function OverviewTab({ deal, onChange }: { deal: DealDetail; onChange: () => void }) {
  const m = deal.metrics;
  const gaps = useAsync(() => api.gaps(deal.id), [deal.id, deal.updated_at]);
  const [form, setForm] = useState({
    stage: deal.stage, summary: deal.summary, business_drivers: deal.business_drivers,
    technical_context: deal.technical_context, target_close: deal.target_close ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await attempt(
      () => api.updateDeal(deal.id, { ...form, target_close: form.target_close || null }), setError);
    if (ok) {
      setSaved(true);
      onChange();
    }
  };

  return (
    <div>
      <div className="metrics">
        <Metric value={m.stakeholders} label="Stakeholders" />
        <Metric value={`${m.questions_answered}/${m.questions_total}`} label="Questions answered" />
        <Metric value={m.requirements} label="Requirements" />
        <Metric value={`${m.criteria_met}/${m.criteria_total}`} label="Criteria met" />
        <Metric value={m.open_tasks} label={`Open tasks (${m.blocked_tasks} blocked, ${m.overdue_tasks} overdue)`} />
        <Metric value={m.gaps_high} label={`High-severity gaps (of ${m.gaps_total})`} />
      </div>
      <div className="grid grid-2">
        <form className="card" onSubmit={save} aria-label="Deal details">
          <h2>Engagement context</h2>
          <ErrorBanner error={error} onDismiss={() => setError(null)} />
          <div className="form-grid">
            <label>
              Stage
              <select value={form.stage} onChange={(e) => { setForm({ ...form, stage: e.target.value }); setSaved(false); }}>
                {STAGES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </label>
            <label>
              Target close
              <input type="date" value={form.target_close} onChange={(e) => { setForm({ ...form, target_close: e.target.value }); setSaved(false); }} />
            </label>
            <label className="full">
              Summary
              <textarea value={form.summary} onChange={(e) => { setForm({ ...form, summary: e.target.value }); setSaved(false); }} />
            </label>
            <label className="full">
              Business drivers
              <textarea value={form.business_drivers} onChange={(e) => { setForm({ ...form, business_drivers: e.target.value }); setSaved(false); }} />
            </label>
            <div className="full">
              <div className="muted small" style={{ marginBottom: 4 }}>Technologies in scope</div>
              <ContextChips value={form.technical_context} onChange={(v) => { setForm({ ...form, technical_context: v }); setSaved(false); }} />
            </div>
          </div>
          <div className="row" style={{ marginTop: "0.8rem" }}>
            <button type="submit">Save</button>
            {saved && <span className="muted small">Saved</span>}
          </div>
          <p className="muted small" style={{ marginTop: "0.6rem" }}>
            Account: {deal.account.name} {deal.account.is_synthetic && "(synthetic)"} · {deal.account.industry} · {deal.account.region}
          </p>
        </form>
        <div className="card">
          <h2>Top gaps &amp; suggested next actions</h2>
          <ErrorBanner error={gaps.error} />
          {gaps.data && <GapsList dealId={deal.id} gaps={gaps.data.gaps} onChange={onChange} limit={6} />}
        </div>
      </div>
    </div>
  );
}
