import { useState } from "react";
import { api } from "../../api";
import type { Task, TaskStatus } from "../../types";
import { attempt, Badge, Empty, ErrorBanner } from "../../ui";

const STATUSES: TaskStatus[] = ["todo", "in_progress", "blocked", "done", "cancelled"];

function TaskRow({ task, titles, onChange, allowDelete }: {
  task: Task; titles: Record<number, string>; onChange: () => void; allowDelete: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    owner: task.owner, due_date: task.due_date ?? "", blocker: task.blocker, evidence_note: task.evidence_note,
  });
  const closed = task.status === "done" || task.status === "cancelled";
  const overdue = !closed && task.due_date && task.due_date < new Date().toISOString().slice(0, 10);

  const patch = async (body: Partial<Task>) => {
    const ok = await attempt(() => api.updateTask(task.id, body), setError);
    if (ok) onChange();
    else setOpen(true);
  };
  const setStatus = (status: TaskStatus) =>
    patch({ status, blocker: form.blocker, evidence_note: form.evidence_note });
  const saveDetails = () =>
    patch({ owner: form.owner, due_date: form.due_date || null, blocker: form.blocker, evidence_note: form.evidence_note });

  return (
    <>
      <tr className={closed ? "closed" : undefined} data-testid={`task-${task.id}`}>
        <td>
          <div>{task.title}</div>
          {task.status === "blocked" && task.blocker && <div className="small" style={{ color: "var(--bad)" }}>Blocked: {task.blocker}</div>}
          {task.waiting_on.length > 0 && (
            <div className="muted small">Waiting on: {task.waiting_on.map((id) => titles[id] ?? `#${id}`).join(", ")}</div>
          )}
          {task.evidence_required && <div className="small"><Badge tone={task.evidence_note ? "good" : "warn"}>evidence {task.evidence_note ? "recorded" : "required"}</Badge></div>}
        </td>
        <td className="small">{task.owner || <span className="muted">—</span>}</td>
        <td className="small">{task.due_date ?? <span className="muted">—</span>} {overdue && <Badge tone="bad">overdue</Badge>}</td>
        <td>
          <select aria-label={`Status for ${task.title}`} value={task.status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </td>
        <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
          <button type="button" className="link small" onClick={() => setOpen((v) => !v)}>{open ? "Close" : "Edit"}</button>
          {allowDelete && (
            <button type="button" className="link small" style={{ marginLeft: 8, color: "var(--bad)" }}
              onClick={() => window.confirm("Delete this task?") && attempt(() => api.deleteTask(task.id), setError).then((ok) => ok && onChange())}>
              Delete
            </button>
          )}
        </td>
      </tr>
      {(open || error) && (
        <tr>
          <td colSpan={5}>
            <ErrorBanner error={error} onDismiss={() => setError(null)} />
            {open && (
              <div className="form-grid">
                {task.description && <p className="full muted small">{task.description}</p>}
                <label>Owner<input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></label>
                <label>Due date<input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></label>
                <label>Blocker<input value={form.blocker} onChange={(e) => setForm({ ...form, blocker: e.target.value })} placeholder="Required when blocked" /></label>
                <label>Evidence note<input value={form.evidence_note} onChange={(e) => setForm({ ...form, evidence_note: e.target.value })} placeholder={task.evidence_required ? "Required to complete" : "Optional"} /></label>
                <div><button type="button" onClick={saveDetails}>Save</button></div>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function TaskTable({ tasks, allTasks, onChange, allowDelete = false, empty = "No tasks." }: {
  tasks: Task[]; allTasks?: Task[]; onChange: () => void; allowDelete?: boolean; empty?: string;
}) {
  if (!tasks.length) return <Empty>{empty}</Empty>;
  const titles = Object.fromEntries((allTasks ?? tasks).map((t) => [t.id, t.title]));
  return (
    <table>
      <thead><tr><th>Task</th><th>Owner</th><th>Due</th><th>Status</th><th></th></tr></thead>
      <tbody>
        {tasks.map((t) => (
          <TaskRow key={`${t.id}-${t.status}-${t.owner}-${t.due_date}-${t.blocker}-${t.evidence_note}`} task={t}
            titles={titles} onChange={onChange} allowDelete={allowDelete} />
        ))}
      </tbody>
    </table>
  );
}
