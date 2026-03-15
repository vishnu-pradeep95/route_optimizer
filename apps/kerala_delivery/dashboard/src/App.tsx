/**
 * App -- Root component for the Kerala LPG Delivery Ops Dashboard.
 *
 * Layout: responsive 3-tier sidebar (full / icon-only / drawer).
 *   - Desktop (>= 1280px): Full 220px sidebar with icons + labels
 *   - Tablet (768-1279px): Collapsed 64px icon-only strip
 *   - Mobile (< 768px): Hidden sidebar, DaisyUI drawer via hamburger
 *
 * Why a left sidebar instead of a horizontal header nav:
 * - Better horizontal space utilization for map-heavy pages (LiveMap)
 * - Scalable to more nav items without cramping the header
 * - Industry-standard for ops dashboards / command centers
 *
 * Why client-side "routing" with state instead of react-router:
 * We only have 4 pages -- adding a router library is overkill.
 * A simple state toggle is easier to understand and has zero bundle cost.
 * If the app grows beyond 5-6 pages, migrate to react-router.
 */

import { useState, useEffect, useCallback } from "react";
import { Upload, Map, ClipboardList, Users, Fuel, Menu, Settings as SettingsIcon } from "lucide-react";
import { UploadRoutes } from "./pages/UploadRoutes";
import { LiveMap } from "./pages/LiveMap";
import { RunHistory } from "./pages/RunHistory";
import { DriverManagement } from "./pages/DriverManagement";
import { Settings } from "./pages/Settings";
import { fetchHealth } from "./lib/api";
import type { HealthResponse } from "./types";
import "./App.css";

/**
 * Pages available in the dashboard.
 * Using a union type instead of an enum because TypeScript's
 * erasableSyntaxOnly setting forbids const enums.
 *
 * "upload" is the default page -- the primary daily workflow is:
 * upload CDCMS -> generate routes -> print QR codes -> drivers scan.
 */
type Page = "upload" | "live-map" | "run-history" | "drivers" | "settings";

/**
 * Navigation items configuration.
 *
 * Why a data-driven nav instead of hardcoded JSX:
 * - Single source of truth for page labels, icons, and order
 * - Easy to add/remove pages without touching layout code
 * - Keeps the render function clean and scannable
 *
 * Icons are lucide-react components -- SVG-based, scalable,
 * consistent stroke width across all sizes.
 */
const NAV_ITEMS: { page: Page; icon: React.ComponentType<{ size?: number }>; label: string }[] = [
  { page: "upload", icon: Upload, label: "Upload & Routes" },
  { page: "live-map", icon: Map, label: "Live Map" },
  { page: "run-history", icon: ClipboardList, label: "Run History" },
  { page: "drivers", icon: Users, label: "Drivers" },
  { page: "settings", icon: SettingsIcon, label: "Settings" },
];

/** Derive a human-readable status summary from the HealthResponse. */
function healthSummaryText(health: HealthResponse | null): string {
  if (!health) return "Checking...";
  if (!health.services) {
    // Legacy response without per-service data
    return health.status === "healthy" || health.status === "ok" ? "All systems operational" : "Offline";
  }
  if (health.status === "healthy") return "All systems operational";
  // Find unhealthy/degraded services for the summary
  const issues: string[] = [];
  for (const [name, svc] of Object.entries(health.services)) {
    if (svc.status !== "connected" && svc.status !== "available" && svc.status !== "configured" && svc.status !== "not_configured") {
      issues.push(name);
    }
  }
  if (health.status === "unhealthy") {
    return issues.length > 0 ? `Unhealthy: ${issues.join(", ")}` : "Unhealthy";
  }
  return issues.length > 0 ? `Degraded: ${issues.join(", ")}` : "Degraded";
}

/** Get the dot color class for a service status. */
function serviceDotClass(status: string): string {
  if (["connected", "available", "configured"].includes(status)) return "healthy";
  if (["not_configured"].includes(status)) return "checking";
  if (["degraded", "timeout"].includes(status)) return "checking";
  return "unhealthy";
}

function App() {
  const [activePage, setActivePage] = useState<Page>("upload");
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);

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
      setHealthData(res);
      setApiHealthy(res.status === "healthy" || res.status === "ok");
    } catch {
      setApiHealthy(false);
      setHealthData(null);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  /** Close the mobile drawer (uncheck the hidden toggle input). */
  const closeDrawer = () => {
    const el = document.getElementById("mobile-drawer") as HTMLInputElement;
    if (el) el.checked = false;
  };

  /** Shared nav button list -- used by both desktop sidebar and mobile drawer. */
  const renderNavItems = (opts?: { onClick?: () => void }) =>
    NAV_ITEMS.map(({ page, icon: Icon, label }) => (
      <button
        key={page}
        className={`sidebar-nav-item ${activePage === page ? "active" : ""}`}
        onClick={() => {
          setActivePage(page);
          opts?.onClick?.();
        }}
        title={label}
      >
        <span className="sidebar-nav-icon"><Icon size={20} /></span>
        <span className="sidebar-nav-label">{label}</span>
      </button>
    ));

  /** Shared health indicator -- used by both desktop sidebar and mobile drawer. */
  const renderHealth = () => (
    <div className="sidebar-health" data-testid="health-status-bar">
      {/* Overall status dot and text */}
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
        {healthSummaryText(healthData)}
      </span>
      {/* Per-service status indicators -- shown when expanded health data available */}
      {healthData?.services && (
        <div className="tw:flex tw:flex-col tw:gap-0.5 tw:mt-1 tw:text-xs tw:opacity-70">
          {Object.entries(healthData.services).map(([name, svc]) => (
            <div key={name} className="tw:flex tw:items-center tw:gap-1">
              <span className={`health-dot ${serviceDotClass(svc.status)}`} style={{ width: 6, height: 6 }} />
              <span className="sidebar-health-label">{name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="tw:drawer">
      <input id="mobile-drawer" type="checkbox" className="tw:drawer-toggle" />

      {/* Drawer content -- everything visible normally */}
      <div className="tw:drawer-content">
        {/* Desktop/Tablet sidebar -- hidden on mobile via CSS */}
        <aside className="app-sidebar">
          {/* Brand -- logo area at top of sidebar */}
          <div className="sidebar-brand">
            <span className="sidebar-brand-icon"><Fuel size={22} /></span>
            <span className="sidebar-brand-text">Kerala LPG</span>
          </div>

          {/* Navigation items */}
          <nav className="sidebar-nav">
            {renderNavItems()}
          </nav>

          {/* Health status indicator -- pinned to bottom of sidebar */}
          <div className="sidebar-footer">
            {renderHealth()}
          </div>
        </aside>

        {/* Mobile hamburger -- only visible below 768px via CSS */}
        <label htmlFor="mobile-drawer" className="mobile-menu-btn" aria-label="Open menu">
          <Menu size={24} />
        </label>

        {/* Main content -- fills remaining space to the right of sidebar */}
        <main className="app-main">
          {activePage === "upload" && <UploadRoutes />}
          {activePage === "live-map" && <LiveMap onNavigateToSettings={() => setActivePage("settings")} />}
          {activePage === "run-history" && <RunHistory />}
          {activePage === "drivers" && <DriverManagement />}
          {activePage === "settings" && <Settings />}
        </main>
      </div>

      {/* Mobile drawer side panel -- slides in from left on mobile */}
      <div className="tw:drawer-side tw:z-[200]">
        <label htmlFor="mobile-drawer" aria-label="Close menu" className="tw:drawer-overlay" />
        <nav className="tw:menu tw:bg-base-200 tw:min-h-full tw:w-64 tw:p-4">
          {/* Drawer brand */}
          <div className="tw:mb-4 tw:flex tw:items-center tw:gap-2 tw:px-2">
            <Fuel size={22} />
            <span className="tw:font-bold">Kerala LPG</span>
          </div>

          {/* Drawer nav items */}
          {NAV_ITEMS.map(({ page, icon: Icon, label }) => (
            <li key={page}>
              <button
                className={activePage === page ? "tw:active" : ""}
                onClick={() => {
                  setActivePage(page);
                  closeDrawer();
                }}
              >
                <Icon size={20} /> {label}
              </button>
            </li>
          ))}

          {/* Drawer health indicator */}
          <div className="tw:mt-auto tw:pt-4 tw:border-t tw:border-base-300">
            {renderHealth()}
          </div>
        </nav>
      </div>
    </div>
  );
}

export default App
