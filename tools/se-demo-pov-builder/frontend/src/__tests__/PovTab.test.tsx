import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PovTab from "../components/deal/PovTab";
import { jsonError, mockApi, WithLibrary } from "../test/helpers";
import type { PovPlan } from "../types";

const plan: PovPlan = {
  id: 9, deal_id: 1, title: "Sample POV", objectives: "Prove it", start_date: "2027-01-01", end_date: "2027-01-31",
  status: "draft", summary_notes: "",
  criteria: [{
    id: 5, deal_id: 1, pov_plan_id: 9, requirement_id: null, title: "Actionable alerts",
    measurable_outcome: ">= 50% actionable", target: "50%", validation_method: "NOC review", owner: "Jo", status: "in_progress",
    notes: "", evidence: [{ id: 1, criterion_id: 5, description: "Lab replay", reference: "", evidence_type: "metric", is_simulated: true, recorded_by: "", recorded_at: "" }],
  }],
  milestones: [],
  checklist: [],
  summary: { criteria_total: 1, criteria_met: 0, must_have_total: 0, must_have_met: 0, completion: 0, milestones_total: 0, milestones_closed: 0, evidence_real: 0, evidence_simulated: 1 },
};

describe("PovTab", () => {
  it("labels simulated evidence and shows the rule when marking met is refused", async () => {
    mockApi({
      "GET /deals/1/pov-plans": () => [plan],
      "GET /deals/1/requirements": () => [],
      "GET /pov-plans/9": () => plan,
      "PATCH /success-criteria/5": () => jsonError(409, "A criterion can only be marked 'met' with at least one real (non-simulated) evidence item"),
    });
    const user = userEvent.setup();
    render(<WithLibrary><PovTab dealId={1} onChange={() => {}} /></WithLibrary>);

    expect(await screen.findByText("SIMULATED — not evidence")).toBeInTheDocument();
    expect(screen.getByText("Simulated (not counted)")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Status for Actionable alerts"), "met");
    expect(await screen.findByRole("alert")).toHaveTextContent("real (non-simulated) evidence");
  });
});
