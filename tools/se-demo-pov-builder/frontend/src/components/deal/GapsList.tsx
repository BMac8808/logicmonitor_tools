import { useState } from "react";
import { api } from "../../api";
import type { Gap } from "../../types";
import { attempt, Empty, ErrorBanner, StatusBadge } from "../../ui";

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
      <table>
        <tbody>
          {shown.map((g) => (
            <tr key={g.code}>
              <td style={{ width: 80 }}><StatusBadge value={g.severity} /></td>
              <td>
                <div>{g.message}</div>
                <div className="muted small">Suggested: {g.suggested_action}</div>
              </td>
              <td style={{ width: 150, textAlign: "right" }}>
                {added.has(g.code) ? (
                  <span className="muted small">Added ✓</span>
                ) : (
                  <button type="button" className="secondary" onClick={() => addAction(g)}>Add next action</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {limit && gaps.length > limit && <p className="muted small">+{gaps.length - limit} more on the Discovery tab.</p>}
    </div>
  );
}
