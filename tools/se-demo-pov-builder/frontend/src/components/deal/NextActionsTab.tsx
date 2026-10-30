import { useState } from "react";
import { api } from "../../api";
import TaskTable from "./TaskTable";
import { attempt, ErrorBanner, useAsync } from "../../ui";

export default function NextActionsTab({ dealId, onChange }: { dealId: number; onChange: () => void }) {
  const tasks = useAsync(() => api.tasks(dealId), [dealId]);
  const [form, setForm] = useState({ title: "", owner: "", due_date: "", description: "", depends_on: "" });
  const [showClosed, setShowClosed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    void tasks.reload();
    onChange();
  };
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await attempt(() => api.createTask(dealId, {
      title: form.title, owner: form.owner, description: form.description, due_date: form.due_date || null,
      depends_on: form.depends_on ? [Number(form.depends_on)] : [],
    }), setError);
    if (ok) {
      setForm({ title: "", owner: "", due_date: "", description: "", depends_on: "" });
      refresh();
    }
  };

  const all = tasks.data ?? [];
  const isOpen = (s: string) => s !== "done" && s !== "cancelled";
  const actions = all.filter((t) => t.kind === "next_action" && (showClosed || isOpen(t.status)));
  const otherOpen = all.filter((t) => t.kind !== "next_action" && isOpen(t.status) && t.due_date);

  return (
    <div>
      <ErrorBanner error={error ?? tasks.error} onDismiss={() => setError(null)} />
      <form className="card" onSubmit={add} aria-label="Add next action">
        <h2>Add next action</h2>
        <div className="form-grid">
          <label className="full">What needs to happen<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>Owner<input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} /></label>
          <label>Due date<input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></label>
          <label>
            Depends on
            <select value={form.depends_on} onChange={(e) => setForm({ ...form, depends_on: e.target.value })}>
              <option value="">Nothing</option>
              {all.filter((t) => isOpen(t.status)).map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </select>
          </label>
          <label className="full">Notes<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        </div>
        <button type="submit" style={{ marginTop: 8 }}>Add next action</button>
      </form>
      <div className="card">
        <div className="row spread">
          <h2>Next actions</h2>
          <label className="inline small"><input type="checkbox" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} />Show completed</label>
        </div>
        <TaskTable tasks={actions} allTasks={all} onChange={refresh} allowDelete empty="No open next actions. Add one, or create them from gaps on the Overview tab." />
      </div>
      <div className="card">
        <h2>Upcoming workflow tasks &amp; milestones</h2>
        <TaskTable tasks={otherOpen} allTasks={all} onChange={refresh} empty="No dated workflow tasks or milestones." />
      </div>
    </div>
  );
}
