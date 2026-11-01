import { useState } from "react";
import { api } from "../../api";
import type { Gap } from "../../types";
import { attempt, Empty, ErrorBanner, Generated, StatusBadge } from "../../ui";

/** Stacked rows (not a table) so the text keeps its width in a narrow side column. */
export default function GapsList({ dealId, gaps, onChange, limit }: {
  dealId: number; gaps: Gap[]; onChange?: () => void; limit?: number;
}) {
  const [added, setAdded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const shown = limit ? gaps.slice(0, limit) : gaps;

  const addAction = (gap: Gap) =>
    attempt(async () => {
      await api.createTask(dealId, { title: gap.suggested_action, description: gap.message });
      setAdded((s) => new Set(s).add(gap.code));
      onChange?.();
    }, setError);

  if (!gaps.length) return <Empty>No gaps detected.</Empty>;
  return (
    <div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      {shown.map((g) => (
        <div key={g.code} className="gap-item">
          <div className="gap-head">
            <StatusBadge value={g.severity} />
            <span>{g.message}</span>
          </div>
          <div className="small gap-actions">
            <Generated label="Suggested next action">Suggested: {g.suggested_action}</Generated>{" "}
            {added.has(g.code) ? (
              <span className="muted">· Added ✓</span>
            ) : (
              <button type="button" className="link small" onClick={() => addAction(g)}>Add next action</button>
            )}
          </div>
        </div>
      ))}
      {limit && gaps.length > limit && <p className="muted small">+{gaps.length - limit} more on the Discovery tab.</p>}
    </div>
  );
}
