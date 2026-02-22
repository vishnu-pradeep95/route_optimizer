/**
 * StatsBar — Summary statistics cards displayed at the top of the Live Map page.
 *
 * Shows aggregate delivery metrics from the latest optimization run.
 * Each card is a simple count with a label and color accent.
 *
 * Why a separate component instead of inline in LiveMap:
 * - Reusable across pages (Live Map, Run History detail)
 * - Easier to test in isolation
 * - Clean separation: StatsBar owns the presentation, parent owns the data
 */

import type { RouteSummary, RouteDetail } from "../types";
import { STATUS_COLORS } from "../types";
import "./StatsBar.css";

interface StatsBarProps {
  /** Route summaries from /api/routes (used for totals). */
  routes: RouteSummary[];
  /** Detailed routes with individual stops (used for status breakdown). */
  routeDetails: RouteDetail[];
  /** Number of orders that couldn't be assigned to any vehicle. */
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

export function StatsBar({ routes, routeDetails, unassignedOrders }: StatsBarProps) {
  const counts = countByStatus(routeDetails);

  return (
    <div className="stats-bar">
      <StatCard
        label="Total Deliveries"
        value={counts.total}
        color={STATUS_COLORS.active}
      />
      <StatCard
        label="Completed"
        value={counts.delivered}
        color={STATUS_COLORS.delivered}
      />
      <StatCard
        label="Pending"
        value={counts.pending}
        color={STATUS_COLORS.pending}
      />
      <StatCard
        label="Failed"
        value={counts.failed}
        color={STATUS_COLORS.failed}
      />
      <StatCard
        label="Vehicles Active"
        value={routes.length}
        color={STATUS_COLORS.active}
      />
      <StatCard
        label="Unassigned"
        value={unassignedOrders}
        color={STATUS_COLORS.failed}
      />
    </div>
  );
}

/** Individual stat card within the bar. */
function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="stat-card" style={{ borderTopColor: color }}>
      <div className="stat-value" style={{ color }}>
        {value}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
