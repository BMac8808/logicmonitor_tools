import { useState } from "react";
import { api } from "../../api";
import TaskTable from "./TaskTable";
import { attempt, Empty, ErrorBanner, StatusBadge, useAsync } from "../../ui";

export default function WorkflowsTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const runs = useAsync(() => api.workflowRuns(dealId), [dealId]);
  const defs = useAsync(() => api.workflows(), []);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    void runs.reload();
    onChange();
  };
  const startedIds = new Set(runs.data?.map((r) => r.workflow_id));
  const available = defs.data?.filter((d) => !startedIds.has(d.id)) ?? [];
  const allTasks = runs.data?.flatMap((r) => r.tasks) ?? [];

  return (
    <div>
      <ErrorBanner error={error ?? runs.error} onDismiss={() => setError(null)} />
      <div className="card row spread">
        <div className="row">
          <select aria-label="Workflow to start" value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">Start a workflow…</option>
            {available.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button type="button" disabled={!choice}
            onClick={() => attempt(() => api.startWorkflow(dealId, choice), setError).then((ok) => { if (ok) { setChoice(""); refresh(); } })}>
            Start
          </button>
        </div>
        <span className="muted small">Workflows are defined in <code>workflows/*.yaml</code>.</span>
      </div>
      {runs.data && !runs.data.length && <Empty>No workflows started for this deal.</Empty>}
      {runs.data?.map((run) => (
        <div key={run.id} className="card">
          <div className="row spread">
            <h2>{run.workflow_name} <span className="muted small">v{run.workflow_version}</span></h2>
            <div className="row">
              {run.complete ? <StatusBadge value="complete" /> : <span className="muted small">{Math.round(run.progress * 100)}% complete</span>}
              <button type="button" className="danger"
                onClick={() => window.confirm(`Remove the ${run.workflow_name} workflow and its tasks?`)
                  && attempt(() => api.deleteWorkflowRun(run.id), setError).then((ok) => ok && refresh())}>
                Remove
              </button>
            </div>
          </div>
          <div className="progress"><span style={{ width: `${Math.round(run.progress * 100)}%` }} /></div>
          <div className="stage-list">
            {run.stages.map((s) => (
              <div key={s.id} className={`stage${s.id === run.current_stage ? " current" : ""}`}>
                {s.name} · {s.closed}/{s.total} {s.blocked > 0 && <StatusBadge value="blocked" />}
              </div>
            ))}
          </div>
          {run.stages.map((s) => (
            <div key={s.id}>
              <h4>{s.name} <StatusBadge value={s.status} /></h4>
              {s.exit_criteria.length > 0 && <p className="muted small">Exit criteria: {s.exit_criteria.join("; ")}</p>}
              <TaskTable tasks={run.tasks.filter((t) => t.stage_id === s.id)} allTasks={allTasks} onChange={refresh} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
