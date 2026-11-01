import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { CapabilityCatalog, ContextTag, DiscoveryLibrary, Ecosystem, Persona } from "./types";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(fn, deps);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await load());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [load]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

/** Runs an action, reporting failures through setError. Returns true on success. */
export async function attempt(action: () => Promise<unknown>, setError: (e: string | null) => void): Promise<boolean> {
  try {
    await action();
    setError(null);
    return true;
  } catch (e) {
    setError(e instanceof Error ? e.message : String(e));
    return false;
  }
}

export function ErrorBanner({ error, onDismiss }: { error: string | null; onDismiss?: () => void }) {
  if (!error) return null;
  return (
    <div className="banner banner-error" role="alert">
      <span>{error}</span>
      {onDismiss && (
        <button type="button" className="link" onClick={onDismiss} aria-label="Dismiss error">
          Dismiss
        </button>
      )}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: string; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/**
 * One colour per state, everywhere:
 * red = blocked/failed, amber = needs attention/TBD, blue = in progress, green = done,
 * purple = simulated, grey = not started. Priorities are not states, so they use an outline.
 */
export type Tone = "bad" | "warn" | "info" | "good" | "sim" | "neutral";

export const STATE_LEGEND: { tone: Tone; label: string }[] = [
  { tone: "bad", label: "Blocked" },
  { tone: "warn", label: "Needs attention / TBD" },
  { tone: "info", label: "In progress" },
  { tone: "good", label: "Done" },
  { tone: "sim", label: "Simulated" },
  { tone: "neutral", label: "Not started" },
];

const STATUS_TONES: Record<string, string> = {
  done: "good", met: "good", complete: "good", completed: "good", confirmed: "good",
  active: "info", in_progress: "info",
  assumed: "warn", tbd: "warn", high: "warn", medium: "warn",
  blocked: "bad", not_met: "bad",
  simulated: "sim",
  todo: "neutral", not_started: "neutral", draft: "neutral", missing: "neutral", low: "neutral",
  waived: "neutral", cancelled: "neutral", closed: "neutral",
  must: "outline-strong", should: "outline", could: "outline",
};

const STATUS_LABELS: Record<string, string> = { missing: "not covered", tbd: "TBD" };

export function toneFor(value: string): string {
  return STATUS_TONES[value] ?? "neutral";
}

export function StatusBadge({ value }: { value: string }) {
  return <Badge tone={toneFor(value)}>{STATUS_LABELS[value] ?? value.replace(/_/g, " ")}</Badge>;
}

export function StateLegend() {
  return (
    <div className="legend" aria-label="Status colours">
      {STATE_LEGEND.map((s) => <span key={s.tone} className="legend-item"><span className={`dot dot-${s.tone}`} />{s.label}</span>)}
    </div>
  );
}

/** Text the app generated (templates, keyword matches, AI) rather than something the user entered. */
export function Generated({ children, label = "Generated", block = false }: { children: ReactNode; label?: string; block?: boolean }) {
  if (block) {
    return <div className="gen gen-block"><span className="gen-label">{label}</span>{children}</div>;
  }
  return <span className="gen" title={`${label} — not entered by you`}>{children}</span>;
}

export function Tile({ tone = "neutral", value, label, hint }: { tone?: Tone; value: ReactNode; label: string; hint?: string }) {
  return (
    <div className={`tile tile-${tone}`} title={hint}>
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

/** One section-level notice instead of a suffix on every unverified capability chip. */
export function UnverifiedNotice({ count, total }: { count: number; total: number }) {
  if (!count) return null;
  return (
    <p className="notice-unverified small">
      <span className="badge badge-unverified">dashed</span>{" "}
      {count === total ? `All ${total}` : `${count} of ${total}`} capabilit{total === 1 ? "y is" : "ies are"} not yet
      verified against official documentation. Check before presenting.
    </p>
  );
}

export function CapabilityChip({ name, verified }: { name: string; verified: boolean }) {
  return <span className={`badge ${verified ? "badge-good" : "badge-unverified"}`} title={verified ? "Verified" : "Not verified"}>{name}</span>;
}

export function SimulatedBadge() {
  return (
    <Badge tone="sim">
      <span title="Produced with mock or simulated data. Not evidence from the customer's environment.">SIMULATED — not evidence</span>
    </Badge>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function downloadText(filename: string, text: string, type = "text/markdown"): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "export";
}

export interface Library {
  personas: Record<string, Persona>;
  personaList: Persona[];
  capabilities: CapabilityCatalog;
  capabilityName: (id: string) => string;
  discovery: DiscoveryLibrary;
  contextTags: ContextTag[];
  ecosystem: Ecosystem;
}

export const LibraryContext = createContext<Library | null>(null);

export function useLibrary(): Library {
  const lib = useContext(LibraryContext);
  if (!lib) throw new Error("LibraryContext not provided");
  return lib;
}

export function buildLibrary(
  personas: Persona[], capabilities: CapabilityCatalog, discovery: DiscoveryLibrary, ecosystem: Ecosystem,
): Library {
  const capNames = Object.fromEntries(capabilities.capabilities.map((c) => [c.id, c.name]));
  return {
    personas: Object.fromEntries(personas.map((p) => [p.id, p])),
    personaList: personas,
    capabilities,
    capabilityName: (id) => capNames[id] ?? id,
    discovery,
    contextTags: discovery.context_tags,
    ecosystem,
  };
}
