import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DealsPage from "../pages/DealsPage";
import { mockApi, WithLibrary } from "../test/helpers";

describe("DealsPage", () => {
  it("shows an empty state and offers the sample engagement", async () => {
    mockApi({ "GET /deals": () => [] });
    render(<WithLibrary><DealsPage allowSample /></WithLibrary>);
    expect(await screen.findByText(/No deals yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load sample engagement" })).toBeInTheDocument();
  });

  it("creates an account (real customer data by default) and a deal with technical context", async () => {
    const calls = mockApi({
      "GET /deals": () => [],
      "GET /accounts": () => [],
      "POST /accounts": (b) => ({ id: 7, ...(b as object) }),
      "POST /deals": (b) => ({ id: 42, ...(b as object) }),
    });
    const user = userEvent.setup();
    render(<WithLibrary><DealsPage allowSample={false} /></WithLibrary>);
    await user.click(await screen.findByRole("button", { name: "New deal" }));
    await user.type(screen.getByLabelText("Account name"), "Example Co (fictional)");
    await user.type(screen.getByLabelText("Deal name"), "Monitoring refresh");
    await user.click(screen.getByRole("button", { name: "Network" }));
    await user.click(screen.getByRole("button", { name: "Create deal" }));

    const dealCall = await vi.waitFor(() => {
      const c = calls.find((x) => x.method === "POST" && x.path === "/deals");
      if (!c) throw new Error("deal not created yet");
      return c;
    });
    expect(dealCall.body).toMatchObject({ account_id: 7, name: "Monitoring refresh", technical_context: ["network"] });
    expect(calls.find((c) => c.path === "/accounts" && c.method === "POST")?.body).toMatchObject({ is_synthetic: false });
    expect(window.location.hash).toBe("#/deals/42/stakeholders");
  });

  it("marks a new account fictional only when asked", async () => {
    const calls = mockApi({
      "GET /deals": () => [],
      "GET /accounts": () => [],
      "POST /accounts": (b) => ({ id: 7, ...(b as object) }),
      "POST /deals": (b) => ({ id: 43, ...(b as object) }),
    });
    const user = userEvent.setup();
    render(<WithLibrary><DealsPage allowSample={false} /></WithLibrary>);
    await user.click(await screen.findByRole("button", { name: "New deal" }));
    await user.type(screen.getByLabelText("Account name"), "Example Co");
    await user.type(screen.getByLabelText("Deal name"), "Demo deal");
    await user.click(screen.getByLabelText("Fictional or sample account (not a real customer)"));
    await user.click(screen.getByRole("button", { name: "Create deal" }));
    await vi.waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/deals")).toBe(true));
    expect(calls.find((c) => c.path === "/accounts" && c.method === "POST")?.body).toMatchObject({ is_synthetic: true });
  });
});
