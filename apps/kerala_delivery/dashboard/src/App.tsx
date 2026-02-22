/**
 * App — Root component for the Kerala LPG Delivery Ops Dashboard.
 *
 * Layout: fixed header + sidebar nav + main content area.
 *
 * Why client-side "routing" with state instead of react-router:
 * We only have 2 pages — adding a router library for 2 pages is overkill.
 * A simple state toggle is easier to understand and has zero bundle cost.
 * If the app grows beyond 3-4 pages, migrate to react-router.
 */

import { useState, useEffect, useCallback } from "react";
import { LiveMap } from "./pages/LiveMap";
import { RunHistory } from "./pages/RunHistory";
import { fetchHealth } from "./lib/api";
import "./App.css";

/** The two pages available in the dashboard. */
type Page = "live-map" | "run-history";

function App() {
  const [activePage, setActivePage] = useState<Page>("live-map");
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  /**
   * Check API health on mount and every 30 seconds.
   *
   * Why poll health instead of relying on data fetch errors:
   * A dedicated health indicator in the header gives operators
   * immediate visibility into backend status without interpreting
   * ambiguous error messages.
   */
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetchHealth();
      setApiHealthy(res.status === "healthy" || res.status === "ok");
    } catch {
      setApiHealthy(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return (
    <div className="app">
      {/* Header — always visible */}
      <header className="app-header">
        <div className="app-title">
          <h1>Kerala LPG Delivery</h1>
          <span className="app-subtitle">Ops Dashboard</span>
        </div>

        {/* Navigation tabs */}
        <nav className="app-nav">
          <button
            className={`nav-tab ${activePage === "live-map" ? "active" : ""}`}
            onClick={() => setActivePage("live-map")}
          >
            🗺 Live Map
          </button>
          <button
            className={`nav-tab ${activePage === "run-history" ? "active" : ""}`}
            onClick={() => setActivePage("run-history")}
          >
            📋 Run History
          </button>
        </nav>

        {/* Health status indicator */}
        <div className="app-health">
          <span
            className={`health-dot ${
              apiHealthy === null
                ? "checking"
                : apiHealthy
                  ? "healthy"
                  : "unhealthy"
            }`}
          />
          <span className="health-label">
            {apiHealthy === null
              ? "Checking..."
              : apiHealthy
                ? "API Connected"
                : "API Offline"}
          </span>
        </div>
      </header>

      {/* Main content — switches based on active page */}
      <main className="app-main">
        {activePage === "live-map" && <LiveMap />}
        {activePage === "run-history" && <RunHistory />}
      </main>
    </div>
  );
}

export default App
