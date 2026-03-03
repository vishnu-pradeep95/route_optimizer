/**
 * StatusBadge -- color-coded status indicator using DaisyUI badge.
 *
 * Maps status strings to DaisyUI semantic badge classes:
 * - delivered/completed -> tw:badge-success (green)
 * - pending/running -> tw:badge-warning (amber)
 * - failed -> tw:badge-error (red)
 *
 * Also exports deriveRouteStatus() for computing route-level status
 * from individual stop statuses (used by UploadRoutes route cards).
 */
import type { RouteStop } from "../types";

type BadgeStatus = "pending" | "delivered" | "failed" | "completed" | "running";

const BADGE_CLASSES: Record<BadgeStatus, string> = {
  delivered: "tw:badge-success",
  completed: "tw:badge-success",
  pending: "tw:badge-warning",
  running: "tw:badge-warning",
  failed: "tw:badge-error",
};

const BADGE_LABELS: Record<BadgeStatus, string> = {
  delivered: "Complete",
  completed: "Completed",
  pending: "Pending",
  running: "Running",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: BadgeStatus }) {
  const badgeClass = BADGE_CLASSES[status] ?? "tw:badge-ghost";
  const label = BADGE_LABELS[status] ?? status;
  return (
    <span className={`tw-badge tw:badge-sm ${badgeClass}`}>{label}</span>
  );
}

/**
 * Derive a route-level status from its stops.
 * - Any failed stops -> 'failed' (issues take priority)
 * - All delivered -> 'delivered' (complete)
 * - Mix of pending + delivered -> 'pending' (in progress)
 * - All pending -> 'pending'
 */
export function deriveRouteStatus(stops: RouteStop[]): BadgeStatus {
  if (stops.length === 0) return "pending";
  const hasFailed = stops.some((s) => s.status === "failed");
  if (hasFailed) return "failed";
  const allDelivered = stops.every((s) => s.status === "delivered");
  if (allDelivered) return "delivered";
  return "pending";
}
