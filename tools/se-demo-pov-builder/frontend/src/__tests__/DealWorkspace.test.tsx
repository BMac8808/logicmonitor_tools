import { render, screen } from "@testing-library/react";
import DealWorkspace from "../pages/DealWorkspace";
import { mockApi, WithLibrary } from "../test/helpers";

const metrics = {
  stakeholders: 0, questions_total: 0, questions_answered: 0, requirements: 0, criteria_total: 0, criteria_met: 0,
  demo_plans: 0, pov_plans: 0, open_tasks: 0, open_next_actions: 0, blocked_tasks: 0, overdue_tasks: 0,
  gaps_high: 0, gaps_total: 0,
};

function deal(overrides: Record<string, unknown>) {
  return {
    id: 4, account_id: 1, name: "Linked deal", stage: "discovery", summary: "", business_drivers: "",
    technical_context: [], target_close: null, updated_at: "2026-10-30T00:00:00Z",
    external_system: null, external_id: null, external_url: null, external_import_link: null,
    account: { id: 1, name: "Acme (fictional)", industry: "", employee_band: "", region: "", notes: "", is_synthetic: true },
    metrics, ...overrides,
  };
}

describe("DealWorkspace header", () => {
  it("offers Send to LMDA for deals linked to an LMDA opportunity", async () => {
    mockApi({
      "GET /deals/4": () => deal({
        external_system: "lmda", external_id: "006POC000000001",
        external_url: "http://localhost:3000/opportunity/006POC000000001",
        external_import_link: "http://localhost:3000/opportunity/006POC000000001/scoping?seBuilderDeal=x",
      }),
      "GET /deals/4/discovery/gaps": () => ({ gaps: [], qualification: [] }),
    });
    render(<WithLibrary><DealWorkspace dealId={4} tab="overview" llmEnabled={false} /></WithLibrary>);
    const send = await screen.findByRole("link", { name: "Send to LMDA" });
    expect(send).toHaveAttribute("href", "http://localhost:3000/opportunity/006POC000000001/scoping?seBuilderDeal=x");
    expect(screen.getByRole("link", { name: "006POC000000001" })).toHaveAttribute("href", "http://localhost:3000/opportunity/006POC000000001");
  });

  it("shows no LMDA link for unlinked deals", async () => {
    mockApi({ "GET /deals/4": () => deal({}), "GET /deals/4/discovery/gaps": () => ({ gaps: [], qualification: [] }) });
    render(<WithLibrary><DealWorkspace dealId={4} tab="overview" llmEnabled={false} /></WithLibrary>);
    await screen.findByText("Linked deal");
    expect(screen.queryByRole("link", { name: "Send to LMDA" })).not.toBeInTheDocument();
  });
});
