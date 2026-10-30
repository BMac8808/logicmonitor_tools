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

const STATUS_TONES: Record<string, string> = {
  done: "good", met: "good", complete: "good", confirmed: "good", active: "info",
  in_progress: "info", todo: "neutral", not_started: "neutral", draft: "neutral",
  blocked: "bad", not_met: "bad", assumed: "warn", waived: "neutral", cancelled: "neutral",
  high: "bad", medium: "warn", low: "neutral", missing: "bad",
  must: "bad", should: "warn", could: "neutral",
};

export function StatusBadge({ value }: { value: string }) {
  return <Badge tone={STATUS_TONES[value] ?? "neutral"}>{value.replace(/_/g, " ")}</Badge>;
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
