/**
 * App — Root component for the Kerala LPG Delivery Ops Dashboard.
 *
 * Layout: collapsible left sidebar (64px → 220px on hover) + main content area.
 *
 * Why a left sidebar instead of a horizontal header nav:
 * - Better horizontal space utilization for map-heavy pages (LiveMap)
 * - Scalable to more nav items without cramping the header
 * - Industry-standard for ops dashboards / command centers
 * - Sidebar collapses to icons-only on narrow focus, expands on hover
 *
 * Why client-side "routing" with state instead of react-router:
 * We only have 4 pages — adding a router library is overkill.
 * A simple state toggle is easier to understand and has zero bundle cost.
 * If the app grows beyond 5-6 pages, migrate to react-router.
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

/**
 * Navigation items configuration.
 *
 * Why a data-driven nav instead of hardcoded JSX:
 * - Single source of truth for page labels, icons, and order
 * - Easy to add/remove pages without touching layout code
 * - Keeps the render function clean and scannable
 */
const NAV_ITEMS: { page: Page; icon: string; label: string }[] = [
  { page: "upload", icon: "📤", label: "Upload & Routes" },
  { page: "live-map", icon: "🗺️", label: "Live Map" },
  { page: "run-history", icon: "📋", label: "Run History" },
  { page: "fleet", icon: "🚛", label: "Fleet" },
];

function App() {
  const [activePage, setActivePage] = useState<Page>("upload");
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  /**
   * Check API health on mount and every 30 seconds.
   *
   * Why poll health instead of relying on data fetch errors:
   * A dedicated health indicator gives operators immediate visibility
   * into backend status without interpreting ambiguous error messages.
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
      {/* Sidebar — collapses to 64px icons, expands to 220px on hover */}
      <aside
        className={`app-sidebar ${sidebarExpanded ? "expanded" : ""}`}
        onMouseEnter={() => setSidebarExpanded(true)}
        onMouseLeave={() => setSidebarExpanded(false)}
      >
        {/* Brand — logo area at top of sidebar */}
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">⛽</span>
          <span className="sidebar-brand-text">Kerala LPG</span>
        </div>

        {/* Navigation items */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ page, icon, label }) => (
            <button
              key={page}
              className={`sidebar-nav-item ${activePage === page ? "active" : ""}`}
              onClick={() => setActivePage(page)}
              title={label}
            >
              <span className="sidebar-nav-icon">{icon}</span>
              <span className="sidebar-nav-label">{label}</span>
            </button>
          ))}
        </nav>

        {/* Health status indicator — pinned to bottom of sidebar */}
        <div className="sidebar-footer">
          <div className="sidebar-health">
            <span
              className={`health-dot ${
                apiHealthy === null
                  ? "checking"
                  : apiHealthy
                    ? "healthy"
                    : "unhealthy"
              }`}
            />
            <span className="sidebar-health-label">
              {apiHealthy === null
                ? "Checking..."
                : apiHealthy
                  ? "Connected"
                  : "Offline"}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content — fills remaining space to the right of sidebar */}
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
