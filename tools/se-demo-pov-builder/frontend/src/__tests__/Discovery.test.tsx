import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DiscoveryTab from "../components/deal/DiscoveryTab";
import { mockApi, WithLibrary } from "../test/helpers";
import type { Question } from "../types";

const q = (over: Partial<Question>): Question => ({
  id: "x", text: "x", category: "technical", purpose: "", listen_for: [], suggests_capabilities: [],
  qualification_key: null, priority: 2, relevant_personas: [], suggested: true, custom: false, answer: null, ...over,
});

const alertNoise = q({
  id: "tech_alert_noise", text: "How many alerts does the team receive in a typical week?", purpose: "Measure alert quality",
  listen_for: ["alert fatigue"], suggests_capabilities: ["alerting_escalation"], priority: 1, relevant_personas: ["practitioner"],
});
const budget = q({ id: "qual_budget", text: "Is budget allocated for this?", category: "qualification", qualification_key: "budget" });
const hidden = q({ id: "tech_kubernetes", text: "Which Kubernetes distributions do you run?", suggested: false });
const custom = q({ id: "custom-1", text: "Which branch sites have no IT staff?", custom: true, suggested: false });

const routes = () => ({
  "GET /deals/1/discovery/questions": () => ({
    questions: [budget, alertNoise, hidden, custom], answered: 0, total: 3, bank_total: 31,
    next_up: [{ question_id: "qual_budget", reason: "Covers checklist item: Budget" }, { question_id: "tech_alert_noise", reason: "Key question for this deal" }],
    unmatched_answers: [],
  }),
  "GET /deals/1/stakeholders": () => [{ id: 3, deal_id: 1, name: "Jo Kim", title: "", persona_id: "practitioner", influence: "medium", stance: "supporter", notes: "" }],
  "GET /deals/1/discovery/gaps": () => ({
    gaps: [{ code: "no_requirements", category: "requirements", severity: "high", message: "No requirements captured yet.", suggested_action: "Turn answers into requirements." }],
    qualification: [{ key: "budget", label: "Budget", description: "", status: "missing", question_ids: ["qual_budget"] }],
  }),
});

describe("DiscoveryTab", () => {
  it("lists questions compactly by category, expands one and saves an answer", async () => {
    const calls = mockApi({
      ...routes(),
      "PUT /deals/1/discovery/answers/tech_alert_noise": (b) => ({ id: 1, question_id: "tech_alert_noise", updated_at: "x", ...(b as object) }),
    });
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<WithLibrary><DiscoveryTab dealId={1} onChange={onChange} llmEnabled={false} /></WithLibrary>);

    const technical = await screen.findByRole("region", { name: "Technical questions" });
    expect(within(technical).getByText(alertNoise.text)).toBeInTheDocument();
    expect(within(technical).getByText(custom.text)).toBeInTheDocument(); // custom questions are always in scope
    expect(screen.queryByText(hidden.text)).not.toBeInTheDocument(); // not suggested for this deal
    expect(screen.queryByLabelText(`Answer to: ${alertNoise.text}`)).not.toBeInTheDocument(); // collapsed
    expect(screen.getByText("No requirements captured yet.")).toBeInTheDocument();
    expect(screen.queryByText(/AI discovery summary/)).not.toBeInTheDocument();

    await user.click(within(technical).getByRole("button", { name: new RegExp(alertNoise.text.slice(0, 20)) }));
    expect(screen.getByText(/Related: Alerting and escalation/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(`Answer to: ${alertNoise.text}`), "About 2,500 a week; most ignored");
    await user.selectOptions(screen.getByLabelText("Answered by"), "3");
    await user.type(screen.getByLabelText("Evidence source"), "NOC call");
    await user.selectOptions(screen.getByLabelText("Confidence"), "assumed");
    await user.click(screen.getByRole("button", { name: "Save answer" }));

    await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toEqual({ answer: "About 2,500 a week; most ignored", evidence_source: "NOC call", confidence: "assumed", stakeholder_id: 3, evidence_quote: null });
  });

  it("shows Start here, filters by checklist item and browses the whole bank", async () => {
    mockApi(routes());
    const user = userEvent.setup();
    render(<WithLibrary><DiscoveryTab dealId={1} onChange={() => {}} llmEnabled={false} /></WithLibrary>);

    const start = await screen.findByLabelText("Start here");
    expect(within(start).getByText("Covers checklist item: Budget")).toBeInTheDocument();
    await user.click(within(start).getByRole("button", { name: budget.text }));
    expect(screen.getByLabelText(`Answer to: ${budget.text}`)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^Budget/ }));
    expect(screen.getByText(/Showing questions for checklist item/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Technical questions" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all" }));

    await user.click(screen.getByRole("button", { name: "All questions" }));
    expect(screen.getByText(hidden.text)).toBeInTheDocument();
    expect(screen.getByText("not suggested")).toBeInTheDocument();
  });

  it("closes the add form once a question is added", async () => {
    const added = q({ id: "custom-2", text: "Which clinics run their own servers?", custom: true, suggested: false });
    mockApi({ ...routes(), "POST /deals/1/discovery/custom-questions": () => added });
    const user = userEvent.setup();
    render(<WithLibrary><DiscoveryTab dealId={1} onChange={() => {}} llmEnabled={false} /></WithLibrary>);

    await user.click(await screen.findByRole("button", { name: "+ Question" }));
    await user.type(screen.getByLabelText("New question"), added.text);
    await user.click(screen.getByRole("button", { name: "Add question" }));
    await vi.waitFor(() => expect(screen.queryByLabelText("New question")).not.toBeInTheDocument());
  });

  it("reviews transcript proposals and saves an accepted one as assumed", async () => {
    const proposal = {
      question_id: "tech_alert_noise", question: alertNoise.text, category: "technical",
      quote: "Honestly around three thousand a week, and the NOC ignores most of them.", speaker: "Dana", timestamp: "00:00:10",
      proposed_answer: "Honestly around three thousand a week, and the NOC ignores most of them.", matched: ["alert fatigue"],
      method: "keyword", score: 6, existing_answer: null, receipt: "r-1",
    };
    const calls = mockApi({
      ...routes(),
      "POST /deals/1/discovery/transcript/proposals": () => ({ format: "text", segments: 4, proposals: [proposal], ai_used: false, notes: [] }),
      "POST /deals/1/discovery/transcript/accept": (b) => ({ id: 9, question_id: "tech_alert_noise", confidence: "assumed", updated_at: "y", ...(b as object) }),
    });
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<WithLibrary><DiscoveryTab dealId={1} onChange={onChange} llmEnabled={false} /></WithLibrary>);

    await user.click(await screen.findByRole("button", { name: "Import transcript / list" }));
    expect(screen.queryByText(/Also ask AI/)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Transcript text"), "Dana: Honestly around three thousand a week");
    await user.click(screen.getByRole("button", { name: "Find answers" }));

    const card = await screen.findByTestId("proposal-tech_alert_noise");
    expect(within(card).getByText(/“Honestly around three thousand/)).toBeInTheDocument();
    expect(within(card).getByText("Dana · 00:00:10")).toBeInTheDocument();
    const box = within(card).getByLabelText(`Proposed answer to: ${alertNoise.text}`);
    await user.clear(box);
    await user.type(box, "About 3,000 alerts a week, mostly ignored");
    await user.click(within(card).getByRole("button", { name: "Accept as assumed" }));

    expect(await within(card).findByText("saved as assumed")).toBeInTheDocument();
    const accept = calls.find((c) => c.path === "/deals/1/discovery/transcript/accept");
    expect(accept?.body).toEqual({
      question_id: "tech_alert_noise", answer: "About 3,000 alerts a week, mostly ignored", quote: proposal.quote,
      speaker: "Dana", timestamp: "00:00:10", filename: "", receipt: "r-1",
    });
    expect(onChange).toHaveBeenCalled();
  });
});
