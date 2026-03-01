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
import { UploadRoutes } from "./pages/UploadRoutes";
import { LiveMap } from "./pages/LiveMap";
import { RunHistory } from "./pages/RunHistory";
import { FleetManagement } from "./pages/FleetManagement";
import { fetchHealth } from "./lib/api";
import "./App.css";

/**
 * Pages available in the dashboard.
 * Using a union type instead of an enum because TypeScript's
 * erasableSyntaxOnly setting forbids const enums.
 *
 * "upload" is the default page — the primary daily workflow is:
 * upload CDCMS → generate routes → print QR codes → drivers scan.
 */
type Page = "upload" | "live-map" | "run-history" | "fleet";

function App() {
  const [activePage, setActivePage] = useState<Page>("upload");
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
            className={`nav-tab ${activePage === "upload" ? "active" : ""}`}
            onClick={() => setActivePage("upload")}
          >
            📤 Upload & Routes
          </button>
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
          <button
            className={`nav-tab ${activePage === "fleet" ? "active" : ""}`}
            onClick={() => setActivePage("fleet")}
          >
            🚛 Fleet
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
        {activePage === "upload" && <UploadRoutes />}
        {activePage === "live-map" && <LiveMap />}
        {activePage === "run-history" && <RunHistory />}
        {activePage === "fleet" && <FleetManagement />}
      </main>
    </div>
  );
}

export default App
