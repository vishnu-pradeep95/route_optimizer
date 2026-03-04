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

export function StatusBadge({ status }: { status: BadgeStatus }) {
  let badgeClass: string;
  let label: string;

  switch (status) {
    case "delivered":
      badgeClass = "tw:badge-success";
      label = "Complete";
      break;
    case "completed":
      badgeClass = "tw:badge-success";
      label = "Completed";
      break;
    case "pending":
      badgeClass = "tw:badge-warning";
      label = "Pending";
      break;
    case "running":
      badgeClass = "tw:badge-warning";
      label = "Running";
      break;
    case "failed":
      badgeClass = "tw:badge-error";
      label = "Failed";
      break;
    default: {
      const _exhaustive: never = status;
      badgeClass = "tw:badge-ghost";
      label = String(_exhaustive);
    }
  }

  return (
    <span className={`tw:badge tw:badge-sm ${badgeClass}`}>{label}</span>
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
