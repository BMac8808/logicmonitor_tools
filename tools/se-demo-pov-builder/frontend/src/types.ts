// Types mirroring the backend schemas (backend/se_pov_builder/schemas.py).

export type Influence = "high" | "medium" | "low";
export type Stance = "supporter" | "neutral" | "skeptic" | "unknown";
export type Confidence = "confirmed" | "assumed";
export type Priority = "must" | "should" | "could";
export type TaskStatus = "todo" | "in_progress" | "blocked" | "done" | "cancelled";
export type CriterionStatus = "not_started" | "in_progress" | "met" | "not_met" | "waived";

export interface Meta {
  name: string;
  version: string;
  disclaimer: string;
  adapter_mode: "mock" | "mcp";
  mcp_url: string;
  llm_provider: string;
  llm_enabled: boolean;
  auth_required: boolean;
  allow_sample_data: boolean;
}

export interface Account {
  id: number;
  name: string;
  industry: string;
  employee_band: string;
  region: string;
  notes: string;
  is_synthetic: boolean;
}

export interface Deal {
  id: number;
  account_id: number;
  name: string;
  stage: string;
  summary: string;
  business_drivers: string;
  technical_context: string[];
  target_close: string | null;
  updated_at: string;
  external_system: string | null;
  external_id: string | null;
  external_url: string | null;
}

export interface DealListItem extends Deal {
  account_name: string;
}

export interface DealMetrics {
  stakeholders: number;
  questions_total: number;
  questions_answered: number;
  requirements: number;
  criteria_total: number;
  criteria_met: number;
  demo_plans: number;
  pov_plans: number;
  open_tasks: number;
  open_next_actions: number;
  blocked_tasks: number;
  overdue_tasks: number;
  gaps_high: number;
  gaps_total: number;
}

export interface DealDetail extends Deal {
  account: Account;
  metrics: DealMetrics;
  external_import_link: string | null;
}

export interface Stakeholder {
  id: number;
  deal_id: number;
  name: string;
  title: string;
  persona_id: string;
  email: string | null;
  influence: Influence;
  stance: Stance;
  notes: string;
}

export interface Objection {
  objection: string;
  approach: string;
}

export interface Persona {
  id: string;
  name: string;
  summary: string;
  coverage: "required" | "recommended" | "optional";
  typical_influence: Influence;
  objectives: string[];
  motivations: string[];
  technical_concerns: string[];
  typical_objections: Objection[];
  discovery_signals: string[];
  influence_notes: string;
  engagement_approach: string[];
  demo_focus: string[];
}

export interface Capability {
  id: string;
  name: string;
  category: string;
  description: string;
  keywords: string[];
  verified: boolean;
}

export interface CapabilityCatalog {
  version: number;
  disclaimer: string;
  capabilities: Capability[];
}

export interface CapabilityMatch {
  capability_id: string;
  name: string;
  verified: boolean;
  matched_keywords: string[];
  from_question: boolean;
  score: number;
}

export interface ContextTag {
  id: string;
  label: string;
}

export interface DiscoveryLibrary {
  context_tags: ContextTag[];
  qualification_checklist: { key: string; label: string; description: string }[];
}

export interface Answer {
  id: number;
  question_id: string;
  stakeholder_id: number | null;
  answer: string;
  evidence_source: string;
  confidence: Confidence;
  updated_at: string;
}

export interface Question {
  id: string;
  text: string;
  category: string;
  purpose: string;
  listen_for: string[];
  suggests_capabilities: string[];
  qualification_key: string | null;
  priority: number;
  relevant_personas: string[];
  answer: Answer | null;
}

export interface DiscoveryQuestions {
  questions: Question[];
  answered: number;
  total: number;
  unmatched_answers: Answer[];
}

export interface Gap {
  code: string;
  category: string;
  severity: "high" | "medium" | "low";
  message: string;
  suggested_action: string;
}

export interface Gaps {
  gaps: Gap[];
  qualification: { key: string; label: string; description: string; status: "confirmed" | "assumed" | "missing" }[];
}

export interface Requirement {
  id: number;
  deal_id: number;
  title: string;
  description: string;
  category: "business" | "technical";
  priority: Priority;
  pain_point: string;
  business_impact: string | null;
  source_question_id: string | null;
  capability_ids: string[];
  status: "draft" | "confirmed";
}

export interface TalkingPoints {
  audience: string;
  persona_id: string | null;
  stakeholders: string[];
  points: string[];
}

export interface DemoSegment {
  scenario_id: string;
  title: string;
  summary: string;
  minutes: number;
  selection_reason: string;
  demonstrates: string[];
  capabilities: { id: string; name: string; verified: boolean }[];
  linked_requirements: { id: number; title: string; priority: Priority; pain_point: string }[];
  matched_keywords: string[];
  talking_points: TalkingPoints[];
  prerequisites: string[];
  data_requirements: string[];
  prep_tasks: string[];
}

export interface DemoPlanContent {
  generator: string;
  generated_at: string;
  duration_minutes: number;
  generic: boolean;
  agenda: { start_minute: number; minutes: number; title: string; kind: string; scenario_id: string | null }[];
  segments: DemoSegment[];
  pain_points: { requirement_id: number; requirement: string; priority: Priority; pain_point: string }[];
  audience_focus: { persona_id: string; persona: string; stakeholders: string[]; focus: string[]; concerns: string[] }[];
  prerequisites: string[];
  data_requirements: string[];
  prep_tasks: string[];
  uncovered_requirements: { id: number; title: string; priority: Priority }[];
  assumptions: string[];
  missing_evidence: string[];
}

export interface DemoPlanSummary {
  id: number;
  version: number;
  title: string;
  duration_minutes: number;
  created_at: string;
}

export interface DemoPlan extends DemoPlanSummary {
  deal_id: number;
  content: DemoPlanContent;
  notes: string;
}

export interface Evidence {
  id: number;
  criterion_id: number;
  description: string;
  reference: string;
  evidence_type: string;
  is_simulated: boolean;
  recorded_by: string;
  recorded_at: string;
}

export interface Criterion {
  id: number;
  deal_id: number;
  pov_plan_id: number | null;
  requirement_id: number | null;
  title: string;
  measurable_outcome: string;
  target: string;
  validation_method: string;
  owner: string;
  status: CriterionStatus;
  notes: string;
  evidence: Evidence[];
}

export interface Task {
  id: number;
  deal_id: number;
  kind: "next_action" | "workflow" | "milestone";
  workflow_run_id: number | null;
  pov_plan_id: number | null;
  stage_id: string | null;
  template_key: string | null;
  title: string;
  description: string;
  owner: string;
  due_date: string | null;
  status: TaskStatus;
  blocker: string;
  depends_on: number[];
  evidence_required: boolean;
  evidence_note: string;
  completed_at: string | null;
  waiting_on: number[];
}

export interface PovPlanSummary {
  id: number;
  deal_id: number;
  title: string;
  objectives: string;
  start_date: string | null;
  end_date: string | null;
  status: "draft" | "active" | "completed" | "closed";
  summary_notes: string;
  portal_group: string | null;
}

export interface PovPlan extends PovPlanSummary {
  criteria: Criterion[];
  milestones: Task[];
  checklist: {
    requirement_id: number | null;
    requirement: string;
    priority: Priority | null;
    items: {
      criterion_id: number;
      title: string;
      status: CriterionStatus;
      owner: string;
      validation_method: string;
      evidence: { real: number; simulated: number };
      ready: boolean;
    }[];
  }[];
  summary: {
    criteria_total: number;
    criteria_met: number;
    must_have_total: number;
    must_have_met: number;
    completion: number;
    milestones_total: number;
    milestones_closed: number;
    evidence_real: number;
    evidence_simulated: number;
  };
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  version: number;
  description: string;
  stages: { id: string; name: string; tasks: { key: string; title: string }[] }[];
}

export interface WorkflowRun {
  id: number;
  workflow_id: string;
  workflow_name: string;
  workflow_version: number;
  stages: { id: string; name: string; status: string; total: number; closed: number; blocked: number; exit_criteria: string[] }[];
  current_stage: string | null;
  progress: number;
  complete: boolean;
  tasks: Task[];
}

export interface DemoScenario {
  id: string;
  title: string;
  summary: string;
  duration_minutes: number;
  capabilities: string[];
  demonstrates: string[];
}

export interface AdapterAction {
  name: string;
  kind: "read_only" | "state_changing";
  description: string;
  params: { name: string; type: string; required: boolean; description: string }[];
}

export interface Adapter {
  id: string;
  name: string;
  description: string;
  mode: string;
  verified: boolean;
  notes: string;
  actions: AdapterAction[];
}

export interface AdapterResult {
  adapter_id: string;
  action: string;
  kind: string;
  simulated: boolean;
  data: unknown;
  message: string;
}

export interface EcosystemProject {
  id: string;
  name: string;
  repo: string;
  commit: string;
  license: string;
  install: string;
  docs: string;
  used_for: string;
}

interface EcosystemItemBase {
  id: string;
  title: string;
  project: string;
  project_name: string;
  license: string;
  source_url: string;
  capabilities: string[];
}

export interface ToolkitItem extends EcosystemItemBase {
  kind: "datasource" | "logsource" | "propertysource" | "suite";
  import: "powershell" | "manual";
  purpose: string;
  milestones: string[];
  requires: string[];
  manual_steps: string;
}

export type EcosystemReference = EcosystemItemBase;

export interface Ecosystem {
  projects: EcosystemProject[];
  toolkit: ToolkitItem[];
  references: EcosystemReference[];
}

export interface ReadinessCheck {
  id: string;
  title: string;
  status: "ok" | "warn" | "fail" | "error";
  detail: string;
  calls: { tool: string; arguments: Record<string, unknown>; total: number | null }[];
}

export interface ReadinessResult {
  group_name: string;
  adapter_mode: string;
  simulated: boolean;
  source: string;
  checked_at: string;
  checks: ReadinessCheck[];
}
