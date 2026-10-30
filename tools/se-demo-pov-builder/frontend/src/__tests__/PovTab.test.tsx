import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PovTab from "../components/deal/PovTab";
import { jsonError, mockApi, WithLibrary } from "../test/helpers";
import type { PovPlan } from "../types";

const plan: PovPlan = {
  id: 9, deal_id: 1, title: "Sample POV", objectives: "Prove it", start_date: "2027-01-01", end_date: "2027-01-31",
  status: "draft", summary_notes: "", portal_group: "POV - Example (fictional)",
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

  it("attaches mock readiness results as simulated evidence and requests the selected toolkit", async () => {
    const calls = mockApi({
      "GET /deals/1/pov-plans": () => [plan],
      "GET /deals/1/requirements": () => [],
      "GET /pov-plans/9": () => plan,
      "POST /pov-plans/9/readiness": () => ({
        group_name: "POV - Example (fictional)", adapter_mode: "mock", simulated: true, source: "mock fixtures (synthetic)",
        checked_at: "2026-10-30T00:00:00Z",
        checks: [{ id: "collectors", title: "Collectors available", status: "warn", detail: "1 of 3 collectors are down",
          calls: [{ tool: "lm_collector", arguments: { operation: "list" }, total: 3 }] }],
      }),
      "POST /success-criteria/5/evidence": (b) => ({ id: 2, criterion_id: 5, ...(b as object) }),
      "POST /pov-plans/9/setup-script": () => new Response("# script", { status: 200, headers: { "Content-Type": "text/plain" } }),
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:x");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const user = userEvent.setup();
    render(<WithLibrary><PovTab dealId={1} onChange={() => {}} /></WithLibrary>);

    await user.click(await screen.findByRole("button", { name: "Run readiness check" }));
    expect(await screen.findByText(/SIMULATED — mock fixtures/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Criterion for Collectors available"), "5");
    await user.click(screen.getByRole("button", { name: "Attach" }));
    await vi.waitFor(() => expect(calls.some((c) => c.path === "/success-criteria/5/evidence")).toBe(true));
    const evidence = calls.find((c) => c.path === "/success-criteria/5/evidence")!.body as Record<string, unknown>;
    expect(evidence.is_simulated).toBe(true);
    expect(String(evidence.reference)).toContain("lm_collector");

    await user.click(screen.getByLabelText("Include NoData metrics"));
    await user.click(screen.getByRole("button", { name: "Download setup script (.ps1)" }));
    await vi.waitFor(() => expect(calls.some((c) => c.path === "/pov-plans/9/setup-script")).toBe(true));
    expect(calls.find((c) => c.path === "/pov-plans/9/setup-script")!.body).toEqual({
      toolkit_ids: ["nodata_metrics"], include_subgroups: true,
    });
  });
});
