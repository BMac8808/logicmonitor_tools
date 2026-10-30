import { useState } from "react";
import { api, getToken, setToken } from "./api";
import { useRoute } from "./router";
import { buildLibrary, ErrorBanner, LibraryContext, useAsync } from "./ui";
import DealsPage from "./pages/DealsPage";
import DealWorkspace from "./pages/DealWorkspace";
import LibraryPage from "./pages/LibraryPage";
import IntegrationsPage from "./pages/IntegrationsPage";

function TokenPrompt({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState(getToken());
  return (
    <form
      className="card narrow"
      onSubmit={(e) => {
        e.preventDefault();
        setToken(value.trim());
        onSaved();
      }}
    >
      <h2>API token required</h2>
      <p>This server was started with <code>SEPB_API_TOKEN</code>. Enter the token to continue.</p>
      <label>
        Token
        <input type="password" value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" />
      </label>
      <button type="submit">Save token</button>
    </form>
  );
}

export default function App() {
  const route = useRoute();
  const meta = useAsync(() => api.meta(), []);
  const library = useAsync(async () => {
    const [personas, capabilities, discovery] = await Promise.all([api.personas(), api.capabilities(), api.discoveryLibrary()]);
    return buildLibrary(personas, capabilities, discovery);
  }, []);

  const needsToken = library.error?.includes("API token");
  const nav = [
    { href: "#/", label: "Deals", active: route.page === "deals" || route.page === "deal" },
    { href: "#/library", label: "Library", active: route.page === "library" },
    { href: "#/integrations", label: "Integrations", active: route.page === "integrations" },
  ];

  return (
    <>
      <header className="topbar">
        <a href="#/" className="brand">SE Demo &amp; POV Builder</a>
        <nav>
          {nav.map((n) => (
            <a key={n.href} href={n.href} className={n.active ? "active" : undefined}>{n.label}</a>
          ))}
        </nav>
        <span className="topbar-note">
          {meta.data ? `v${meta.data.version} · adapters: ${meta.data.adapter_mode} · AI: ${meta.data.llm_enabled ? meta.data.llm_provider : "off"}` : ""}
        </span>
      </header>
      <main>
        {needsToken ? (
          <TokenPrompt onSaved={() => { void library.reload(); void meta.reload(); }} />
        ) : library.error ? (
          <ErrorBanner error={`Could not reach the API: ${library.error}`} />
        ) : !library.data ? (
          <p className="muted">Loading…</p>
        ) : (
          <LibraryContext.Provider value={library.data}>
            {route.page === "deals" && <DealsPage allowSample={meta.data?.allow_sample_data ?? true} />}
            {route.page === "deal" && <DealWorkspace dealId={route.dealId} tab={route.tab} llmEnabled={!!meta.data?.llm_enabled} />}
            {route.page === "library" && <LibraryPage onReloaded={() => void library.reload()} />}
            {route.page === "integrations" && <IntegrationsPage />}
          </LibraryContext.Provider>
        )}
      </main>
      <footer className="footer">
        Community tool — not an official LogicMonitor product. Use synthetic data only. Capability descriptions are
        unverified community summaries.
      </footer>
    </>
  );
}
