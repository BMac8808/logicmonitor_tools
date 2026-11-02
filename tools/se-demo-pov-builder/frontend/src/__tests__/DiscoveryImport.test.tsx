import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DiscoveryImport from "../components/deal/DiscoveryImport";
import { mockApi } from "../test/helpers";

describe("DiscoveryImport question list", () => {
  it("leaves likely duplicates unticked and only hints at possible ones", async () => {
    mockApi({
      "POST /deals/1/discovery/question-list/proposals": () => ({
        proposals: [
          { text: "How many monitoring tools do you run today?", category: "business", duplicate_of: "biz_tool_cost",
            duplicate_text: "How many monitoring tools do you run today, and what do they cost?", duplicate_level: "likely" },
          { text: "Roughly how many alerts do you get each week?", category: "technical", duplicate_of: "tech_alert_noise",
            duplicate_text: "How many alerts does the team receive in a typical week?", duplicate_level: "possible" },
          { text: "Do you monitor UPS power?", category: "technical", duplicate_of: null, duplicate_text: null,
            duplicate_level: null },
        ],
      }),
    });
    const user = userEvent.setup();
    render(<DiscoveryImport dealId={1} llmEnabled={false} questions={[]} onSaved={vi.fn()} onClose={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Question list" }));
    await user.type(screen.getByLabelText("Question list text"), "- anything");
    await user.click(screen.getByRole("button", { name: "Find questions" }));

    expect(await screen.findByLabelText("Add: How many monitoring tools do you run today?")).not.toBeChecked();
    expect(screen.getByLabelText("Add: Roughly how many alerts do you get each week?")).toBeChecked();
    expect(screen.getByLabelText("Add: Do you monitor UPS power?")).toBeChecked();
    expect(screen.getByText(/^Similar to an existing question:/)).toBeInTheDocument();
    expect(screen.getByText(/^Possibly similar to an existing question:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 2 question(s) to this deal" })).toBeEnabled();
  });
});
