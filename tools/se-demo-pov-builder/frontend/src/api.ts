// Thin typed client for the backend API. All requests go to the same origin (/api).
import type {
  Account, Adapter, AdapterResult, Answer, CapabilityCatalog, CapabilityMatch, Criterion, Deal, DealDetail,
  DealListItem, DemoPlan, DemoPlanSummary, DemoScenario, DiscoveryLibrary, DiscoveryQuestions, Evidence, Gaps,
  Meta, Persona, PovPlan, PovPlanSummary, Requirement, Stakeholder, Task, WorkflowDefinition, WorkflowRun,
} from "./types";

const TOKEN_KEY = "sepb_api_token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable; token only lives for this page */
  }
}

function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? JSON.stringify(d)).join("; ");
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  return JSON.stringify(detail);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let message = res.statusText;
    try {
      message = errorMessage((await res.json()).detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const get = <T>(p: string) => request<T>("GET", p);
const post = <T>(p: string, b: unknown = {}) => request<T>("POST", p, b);
const put = <T>(p: string, b: unknown) => request<T>("PUT", p, b);
const patch = <T>(p: string, b: unknown) => request<T>("PATCH", p, b);
const del = (p: string) => request<void>("DELETE", p);

export const api = {
  meta: () => get<Meta>("/meta"),
  loadSample: () => post<{ deal_id: number; created: boolean }>("/sample-data"),

  personas: () => get<Persona[]>("/library/personas"),
  capabilities: () => get<CapabilityCatalog>("/library/capabilities"),
  matchCapabilities: (text: string, source_question_id?: string | null) =>
    post<CapabilityMatch[]>("/library/capabilities/match", { text, source_question_id }),
  discoveryLibrary: () => get<DiscoveryLibrary>("/library/discovery"),
  scenarios: () => get<DemoScenario[]>("/library/demo-scenarios"),
  workflows: () => get<WorkflowDefinition[]>("/library/workflows"),
  reloadContent: () => post<Record<string, number>>("/library/reload"),

  accounts: () => get<Account[]>("/accounts"),
  createAccount: (body: Partial<Account>) => post<Account>("/accounts", body),
  deals: () => get<DealListItem[]>("/deals"),
  deal: (id: number) => get<DealDetail>(`/deals/${id}`),
  createDeal: (body: Partial<Deal>) => post<Deal>("/deals", body),
  updateDeal: (id: number, body: Partial<Deal>) => patch<Deal>(`/deals/${id}`, body),
  deleteDeal: (id: number) => del(`/deals/${id}`),

  stakeholders: (dealId: number) => get<Stakeholder[]>(`/deals/${dealId}/stakeholders`),
  addStakeholder: (dealId: number, body: Partial<Stakeholder>) => post<Stakeholder>(`/deals/${dealId}/stakeholders`, body),
  updateStakeholder: (id: number, body: Partial<Stakeholder>) => patch<Stakeholder>(`/stakeholders/${id}`, body),
  deleteStakeholder: (id: number) => del(`/stakeholders/${id}`),

  questions: (dealId: number) => get<DiscoveryQuestions>(`/deals/${dealId}/discovery/questions`),
  saveAnswer: (dealId: number, questionId: string, body: Partial<Answer>) =>
    put<Answer>(`/deals/${dealId}/discovery/answers/${questionId}`, body),
  deleteAnswer: (dealId: number, questionId: string) => del(`/deals/${dealId}/discovery/answers/${questionId}`),
  gaps: (dealId: number) => get<Gaps>(`/deals/${dealId}/discovery/gaps`),

  requirements: (dealId: number) => get<Requirement[]>(`/deals/${dealId}/requirements`),
  createRequirement: (dealId: number, body: Omit<Partial<Requirement>, "capability_ids"> & { capability_ids?: string[] | null }) =>
    post<Requirement>(`/deals/${dealId}/requirements`, body),
  updateRequirement: (id: number, body: Partial<Requirement>) => patch<Requirement>(`/requirements/${id}`, body),
  deleteRequirement: (id: number) => del(`/requirements/${id}`),

  demoPlans: (dealId: number) => get<DemoPlanSummary[]>(`/deals/${dealId}/demo-plans`),
  demoPlan: (id: number) => get<DemoPlan>(`/demo-plans/${id}`),
  generateDemoPlan: (dealId: number, body: { duration_minutes: number; max_scenarios: number; title?: string }) =>
    post<DemoPlan>(`/deals/${dealId}/demo-plans`, body),
  exportDemoPlan: (id: number) => get<string>(`/demo-plans/${id}/export`),

  povPlans: (dealId: number) => get<PovPlanSummary[]>(`/deals/${dealId}/pov-plans`),
  povPlan: (id: number) => get<PovPlan>(`/pov-plans/${id}`),
  createPovPlan: (dealId: number, body: { title: string; objectives: string; start_date: string; duration_days?: number; draft_criteria_from_requirements: boolean }) =>
    post<PovPlan>(`/deals/${dealId}/pov-plans`, body),
  updatePovPlan: (id: number, body: Partial<PovPlanSummary>) => patch<PovPlan>(`/pov-plans/${id}`, body),
  exportPovPlan: (id: number) => get<string>(`/pov-plans/${id}/export`),

  criteria: (dealId: number) => get<Criterion[]>(`/deals/${dealId}/success-criteria`),
  createCriterion: (dealId: number, body: Partial<Criterion>) => post<Criterion>(`/deals/${dealId}/success-criteria`, body),
  updateCriterion: (id: number, body: Partial<Criterion>) => patch<Criterion>(`/success-criteria/${id}`, body),
  deleteCriterion: (id: number) => del(`/success-criteria/${id}`),
  addEvidence: (criterionId: number, body: Partial<Evidence>) => post<Evidence>(`/success-criteria/${criterionId}/evidence`, body),
  deleteEvidence: (id: number) => del(`/evidence/${id}`),

  workflowRuns: (dealId: number) => get<WorkflowRun[]>(`/deals/${dealId}/workflows`),
  startWorkflow: (dealId: number, workflow_id: string) => post<WorkflowRun>(`/deals/${dealId}/workflows`, { workflow_id }),
  deleteWorkflowRun: (id: number) => del(`/workflow-runs/${id}`),
  tasks: (dealId: number, query = "") => get<Task[]>(`/deals/${dealId}/tasks${query}`),
  createTask: (dealId: number, body: Partial<Task>) => post<Task>(`/deals/${dealId}/tasks`, body),
  updateTask: (id: number, body: Partial<Task>) => patch<Task>(`/tasks/${id}`, body),
  deleteTask: (id: number) => del(`/tasks/${id}`),

  adapters: () => get<Adapter[]>("/adapters"),
  runAdapterAction: (adapterId: string, action: string, body: { params?: Record<string, unknown>; authorization?: unknown }) =>
    post<AdapterResult>(`/adapters/${adapterId}/actions/${action}`, body),

  llmSummary: (dealId: number) => post<{ draft: string; label: string; provider: string }>(`/deals/${dealId}/llm/discovery-summary`),
};
