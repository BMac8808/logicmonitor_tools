import { api, ApiError, setToken } from "../api";
import { jsonError, mockApi } from "../test/helpers";

describe("api client", () => {
  afterEach(() => setToken(""));

  it("sends JSON and the optional bearer token", async () => {
    setToken("abc");
    const calls = mockApi({ "POST /accounts": (b) => ({ id: 1, ...(b as object) }) });
    const account = await api.createAccount({ name: "Example (fictional)" });
    expect(account.id).toBe(1);
    expect(calls[0].headers.Authorization).toBe("Bearer abc");
    expect(calls[0].body).toEqual({ name: "Example (fictional)" });
  });

  it("surfaces backend error details", async () => {
    mockApi({ "PATCH /success-criteria/5": () => jsonError(409, "needs real evidence") });
    await expect(api.updateCriterion(5, { status: "met" })).rejects.toEqual(new ApiError(409, "needs real evidence"));
  });
});
