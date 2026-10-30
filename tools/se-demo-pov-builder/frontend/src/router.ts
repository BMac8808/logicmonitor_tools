// Minimal hash router: #/, #/deals/12/discovery, #/library, #/integrations
import { useEffect, useState } from "react";

export type Route =
  | { page: "deals" }
  | { page: "deal"; dealId: number; tab: string }
  | { page: "library" }
  | { page: "integrations" };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "deals" && parts[1] && /^\d+$/.test(parts[1])) {
    return { page: "deal", dealId: Number(parts[1]), tab: parts[2] ?? "overview" };
  }
  if (parts[0] === "library") return { page: "library" };
  if (parts[0] === "integrations") return { page: "integrations" };
  return { page: "deals" };
}

export function navigate(path: string): void {
  window.location.hash = path;
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
