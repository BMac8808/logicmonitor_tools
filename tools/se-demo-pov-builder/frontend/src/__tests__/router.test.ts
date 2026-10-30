import { parseHash } from "../router";

describe("parseHash", () => {
  it("parses deal routes with tabs", () => {
    expect(parseHash("#/deals/12/discovery")).toEqual({ page: "deal", dealId: 12, tab: "discovery" });
    expect(parseHash("#/deals/3")).toEqual({ page: "deal", dealId: 3, tab: "overview" });
  });
  it("falls back to deals list", () => {
    expect(parseHash("")).toEqual({ page: "deals" });
    expect(parseHash("#/deals/abc")).toEqual({ page: "deals" });
    expect(parseHash("#/library")).toEqual({ page: "library" });
  });
});
