import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DiscoveryTab from "../components/deal/DiscoveryTab";
import { mockApi, WithLibrary } from "../test/helpers";
import type { Question } from "../types";

const question: Question = {
  id: "tech_alert_noise", text: "How many alerts does the team receive in a typical week?", category: "technical",
  purpose: "Measure alert quality", listen_for: ["alert fatigue"], suggests_capabilities: ["alerting_escalation"],
  qualification_key: null, priority: 1, relevant_personas: ["practitioner"], answer: null,
};

describe("DiscoveryTab", () => {
  it("saves an answer with source and confidence", async () => {
    const calls = mockApi({
      "GET /deals/1/discovery/questions": () => ({ questions: [question], answered: 0, total: 1, unmatched_answers: [] }),
      "GET /deals/1/stakeholders": () => [{ id: 3, deal_id: 1, name: "Jo Kim", title: "", persona_id: "practitioner", influence: "medium", stance: "supporter", notes: "" }],
      "GET /deals/1/discovery/gaps": () => ({ gaps: [{ code: "no_requirements", category: "requirements", severity: "high", message: "No requirements captured yet.", suggested_action: "Turn answers into requirements." }], qualification: [{ key: "pain", label: "Primary pain", description: "", status: "missing" }] }),
      "PUT /deals/1/discovery/answers/tech_alert_noise": (b) => ({ id: 1, question_id: "tech_alert_noise", updated_at: "x", ...(b as object) }),
    });
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<WithLibrary><DiscoveryTab dealId={1} onChange={onChange} llmEnabled={false} /></WithLibrary>);

    const textarea = await screen.findByLabelText(question.text);
    expect(screen.getByText(/Related: Alerting and escalation/)).toBeInTheDocument();
    expect(screen.getByText("No requirements captured yet.")).toBeInTheDocument();
    expect(screen.queryByText(/AI discovery summary/)).not.toBeInTheDocument();

    await user.type(textarea, "About 2,500 a week; most ignored");
    await user.selectOptions(screen.getByLabelText("Answered by"), "3");
    await user.type(screen.getByLabelText("Evidence source"), "NOC call");
    await user.selectOptions(screen.getByLabelText("Confidence"), "assumed");
    await user.click(screen.getByRole("button", { name: "Save answer" }));

    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({ answer: "About 2,500 a week; most ignored", evidence_source: "NOC call", confidence: "assumed", stakeholder_id: 3 });
  });
});
