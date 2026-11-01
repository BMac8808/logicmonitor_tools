import { useState } from "react";
import { api } from "../../api";
import type { DealDetail } from "../../types";
import ContextChips from "../ContextChips";
import GapsList from "./GapsList";
import { attempt, ErrorBanner, Tile, useAsync } from "../../ui";

const STAGES = ["discovery", "technical_qualification", "demo_preparation", "pov_planning", "pov_execution",
  "success_validation", "technical_handoff", "closed_won", "closed_lost"];

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
      <div className="tiles" aria-label="Deal summary">
        <Tile tone={m.stakeholders ? "info" : "neutral"} value={m.stakeholders} label="Stakeholders" />
        <Tile tone={!m.questions_answered ? "neutral" : m.questions_answered === m.questions_total ? "good" : "info"}
          value={`${m.questions_answered}/${m.questions_total}`} label="Questions answered" />
        <Tile tone={m.requirements ? "info" : "neutral"} value={m.requirements} label="Requirements" />
        <Tile tone={m.criteria_total && m.criteria_met === m.criteria_total ? "good" : m.criteria_met ? "info" : "neutral"}
          value={`${m.criteria_met}/${m.criteria_total}`} label="Criteria met" />
        <Tile tone={m.blocked_tasks ? "bad" : m.overdue_tasks ? "warn" : m.open_tasks ? "info" : "neutral"} value={m.open_tasks}
          label={`Open tasks (${m.blocked_tasks} blocked, ${m.overdue_tasks} overdue)`} />
        <Tile tone={m.gaps_high ? "warn" : "good"} value={m.gaps_high} label={`High-severity gaps (of ${m.gaps_total})`} />
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
