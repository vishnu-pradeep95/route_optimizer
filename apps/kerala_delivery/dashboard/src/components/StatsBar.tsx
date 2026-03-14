/**
 * StatsBar — Elevated metric tiles displayed at the top of the Live Map page.
 *
 * Design: Industrial-utilitarian tiles with 4px left accent borders,
 * large DM Sans numbers, and IBM Plex Mono labels. Each card has a
 * subtle elevation shadow to separate it from the background.
 *
 * Why a separate component instead of inline in LiveMap:
 * - Reusable across pages (Live Map, Run History detail)
 * - Easier to test in isolation
 * - Clean separation: StatsBar owns the presentation, parent owns the data
 */

import type { RouteSummary, RouteDetail } from "../types";
import "./StatsBar.css";

interface StatsBarProps {
  /** Route summaries from /api/routes (used for totals). */
  routes: RouteSummary[];
  /** Detailed routes with individual stops (used for status breakdown). */
  routeDetails: RouteDetail[];
  /** Number of orders that couldn't be assigned to any driver. */
  unassignedOrders: number;
}

/**
 * Compute delivery status counts from all stops across all routes.
 *
 * Why we count from routeDetails instead of route summaries:
 * Route summaries only have totals; we need per-stop status to show
 * the delivered/pending/failed breakdown.
 */
function countByStatus(routeDetails: RouteDetail[]) {
  let delivered = 0;
  let pending = 0;
  let failed = 0;

  for (const route of routeDetails) {
    for (const stop of route.stops) {
      switch (stop.status) {
        case "delivered":
          delivered++;
          break;
        case "pending":
          pending++;
          break;
        case "failed":
          failed++;
          break;
      }
    }
  }

  return { delivered, pending, failed, total: delivered + pending + failed };
}

/**
 * Color mapping for stat card accent borders.
 *
 * Why separate from STATUS_COLORS?
 * These are design-system accent colors (amber/green/red) that match
 * the new design tokens, not the legacy blue-based status colors.
 * Each stat type gets a distinct left-border accent for quick scanning.
 */
const STAT_ACCENTS = {
  total: "var(--color-info)",
  delivered: "var(--color-success)",
  pending: "var(--color-accent)",
  failed: "var(--color-danger)",
  active: "var(--color-accent)",
  unassigned: "var(--color-danger)",
} as const;

export function StatsBar({ routes, routeDetails, unassignedOrders }: StatsBarProps) {
  const counts = countByStatus(routeDetails);

  return (
    <div className="stats-bar">
      <StatCard
        label="Total Deliveries"
        value={counts.total}
        accent={STAT_ACCENTS.total}
      />
      <StatCard
        label="Completed"
        value={counts.delivered}
        accent={STAT_ACCENTS.delivered}
      />
      <StatCard
        label="Pending"
        value={counts.pending}
        accent={STAT_ACCENTS.pending}
      />
      <StatCard
        label="Failed"
        value={counts.failed}
        accent={STAT_ACCENTS.failed}
      />
      <StatCard
        label="Drivers Active"
        value={routes.length}
        accent={STAT_ACCENTS.active}
        showPulse
      />
      <StatCard
        label="Unassigned"
        value={unassignedOrders}
        accent={STAT_ACCENTS.unassigned}
      />
    </div>
  );
}

/** Individual stat card within the bar. */
function StatCard({
  label,
  value,
  accent,
  showPulse = false,
}: {
  label: string;
  value: number;
  accent: string;
  showPulse?: boolean;
}) {
  return (
    <div className="stat-card" style={{ borderLeftColor: accent }}>
      <div className="stat-value numeric">{value}</div>
      <div className="stat-label">
        {showPulse && value > 0 && <span className="stat-pulse" />}
        {label}
      </div>
    </div>
  );
}
