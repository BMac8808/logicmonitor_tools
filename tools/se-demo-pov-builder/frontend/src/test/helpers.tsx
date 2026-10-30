import type { ReactNode } from "react";
import { vi } from "vitest";
import { buildLibrary, LibraryContext } from "../ui";
import type { Persona } from "../types";

type Handler = (body: unknown) => unknown | Response;

/** Mocks fetch by "METHOD /path" (query string ignored). Returns the list of calls made. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; body: unknown; headers: Record<string, string> }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const path = url.replace(/^\/api/, "").split("?")[0];
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body, headers: (init?.headers ?? {}) as Record<string, string> });
    const handler = routes[`${method} ${path}`];
    if (!handler) return new Response(JSON.stringify({ detail: `No mock for ${method} ${path}` }), { status: 404 });
    const result = handler(body);
    if (result instanceof Response) return result;
    return new Response(JSON.stringify(result), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  return calls;
}

export function jsonError(status: number, detail: string) {
  return new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });
}

const persona = (id: string, name: string, coverage: Persona["coverage"]): Persona => ({
  id, name, coverage, summary: `${name} summary`, typical_influence: "high", objectives: [], motivations: [],
  technical_concerns: [], typical_objections: [], discovery_signals: [], influence_notes: "",
  engagement_approach: [], demo_focus: [],
});

export const testLibrary = buildLibrary(
  [persona("champion", "Champion", "required"), persona("practitioner", "Practitioner", "recommended")],
  {
    version: 1, disclaimer: "Community summaries. Verify.",
    capabilities: [{ id: "alerting_escalation", name: "Alerting and escalation", category: "Ops", description: "", keywords: ["alert"], verified: false }],
  },
  { context_tags: [{ id: "network", label: "Network" }], qualification_checklist: [] },
  {
    projects: [{ id: "lm_powershell_module", name: "Logic.Monitor PowerShell module", repo: "logicmonitor/lm-powershell-module", commit: "7742672a1c7354e9b1b65aef8d053a0094235254", license: "MPL-2.0", install: "Install-Module -Name Logic.Monitor -Scope CurrentUser", docs: "https://example.invalid/docs", used_for: "" }],
    toolkit: [{ id: "nodata_metrics", title: "NoData metrics", project: "logicmonitor_dashboards", project_name: "LogicMonitor-Dashboards", license: "MPL-2.0", source_url: "https://github.com/x/y", capabilities: [], kind: "datasource", import: "powershell", purpose: "Counts NaN datapoints", milestones: ["coverage_validation"], requires: [], manual_steps: "" }],
    references: [],
  },
);

export function WithLibrary({ children }: { children: ReactNode }) {
  return <LibraryContext.Provider value={testLibrary}>{children}</LibraryContext.Provider>;
}
