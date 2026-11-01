import { render, screen, within } from "@testing-library/react";
import DemoPlanTab from "../components/deal/DemoPlanTab";
import RequirementsTab from "../components/deal/RequirementsTab";
import { mockApi, WithLibrary } from "../test/helpers";
import type { DemoPlan, Question, Requirement } from "../types";

const requirement: Requirement = {
  id: 4, deal_id: 1, title: "Monitor branch WAN links", description: "", category: "technical", priority: "must",
  pain_point: "Branches report outages first", business_impact: null, source_question_id: "tech_network",
  capability_ids: ["alerting_escalation"], status: "draft",
};
const question: Question = {
  id: "tech_network", text: "Which network devices and sites need monitoring?", category: "technical", purpose: "",
  listen_for: [], suggests_capabilities: [], qualification_key: null, priority: 2, relevant_personas: [], suggested: true,
  custom: false, answer: { id: 1, question_id: "tech_network", stakeholder_id: null, answer: "12 branches on SD-WAN",
    evidence_source: "Call on 3 Oct", confidence: "assumed", updated_at: "x" },
};

describe("Requirements and plan visuals", () => {
  it("shows the source question and its saved answer instead of the raw id", async () => {
    mockApi({
      "GET /deals/1/requirements": () => [requirement],
      "GET /deals/1/discovery/questions": () => ({ questions: [question], answered: 1, total: 1, bank_total: 31, next_up: [], unmatched_answers: [] }),
    });
    render(<WithLibrary><RequirementsTab dealId={1} onChange={() => {}} /></WithLibrary>);
    expect(await screen.findByText(question.text)).toBeInTheDocument();
    expect(screen.getByText("“12 branches on SD-WAN”")).toBeInTheDocument();
    expect(screen.queryByText("tech_network")).not.toBeInTheDocument();
    expect(screen.getByText(/1 capability is not yet/)).toBeInTheDocument(); // one notice, not a suffix per chip
  });

  it("summarises the demo plan in tiles and calls out uncovered requirements", async () => {
    const plan: DemoPlan = {
      id: 7, deal_id: 1, version: 1, title: "Demo", duration_minutes: 45, created_at: "2026-11-01T00:00:00Z", notes: "",
      content: {
        generator: "x", generated_at: "x", duration_minutes: 45, generic: false,
        agenda: [{ start_minute: 0, minutes: 45, title: "All", kind: "scenario", scenario_id: "s1" }],
        segments: [{
          scenario_id: "s1", title: "Alert triage", summary: "Show alert routing", minutes: 20, selection_reason: "Matches alert noise",
          demonstrates: [], capabilities: [{ id: "alerting_escalation", name: "Alerting and escalation", verified: false },
            { id: "dashboards", name: "Dashboards", verified: false }],
          linked_requirements: [{ id: 1, title: "Cut alert noise", priority: "must", pain_point: "" }],
          matched_keywords: [], talking_points: [], prerequisites: [], data_requirements: [], prep_tasks: [],
        }],
        pain_points: [], audience_focus: [], prerequisites: [], data_requirements: [], prep_tasks: [],
        uncovered_requirements: [{ id: 4, title: "Monitor branch WAN links", priority: "must" }],
        assumptions: [], missing_evidence: [],
      },
    };
    mockApi({ "GET /deals/1/demo-plans": () => [plan], "GET /demo-plans/7": () => plan });
    render(<WithLibrary><DemoPlanTab dealId={1} onChange={() => {}} /></WithLibrary>);

    const tiles = await screen.findByLabelText("Demo plan summary");
    expect(within(tiles).getByText("1/2").closest(".tile")).toHaveClass("tile-warn");
    const callout = screen.getByRole("note", { name: "Requirements not covered" });
    expect(within(callout).getByText("Monitor branch WAN links")).toBeInTheDocument();
    expect(screen.getAllByText(/not yet verified/)).toHaveLength(1);
    expect(screen.queryByText(/· unverified/)).not.toBeInTheDocument();
  });
});
