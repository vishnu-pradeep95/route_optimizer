/**
 * ErrorBanner -- Contextual error display with severity, retry, help, and details.
 *
 * Renders a DaisyUI alert component color-coded by error severity:
 * - Red (tw:alert-error) for upload failures, auth errors
 * - Amber (tw:alert-warning) for timeouts, unavailable services
 * - Blue (tw:alert-info) for degraded service, informational
 *
 * Features:
 * - Prominent user_message text
 * - Clickable help URL (opens docs in new tab)
 * - ErrorDetail collapse for request_id, error_code, timestamp
 * - Retry button (when onRetry callback provided)
 * - Auto-dismiss when connection restores (when autoRecover is true)
 *   with 5-second debounce to avoid flicker on intermittent connectivity
 *
 * See: .planning/phases/02-error-handling-infrastructure/02-RESEARCH.md Pattern 5
 */

import { useEffect, useRef } from "react";
import { AlertTriangle, Info, RefreshCw, ExternalLink, X } from "lucide-react";
import type { ApiError } from "../lib/errors";
import { classifyError, type ErrorSeverity } from "../lib/errors";
import { ErrorDetail } from "./ErrorDetail";
import { fetchHealth } from "../lib/api";

interface ErrorBannerProps {
  error: ApiError;
  onRetry?: () => void;
  onDismiss?: () => void;
  /** When true, auto-dismiss after health check succeeds for 5+ seconds. */
  autoRecover?: boolean;
}

/**
 * Map severity to DaisyUI alert class.
 */
function alertClass(severity: ErrorSeverity): string {
  switch (severity) {
    case "error":
      return "tw:alert-error";
    case "warning":
      return "tw:alert-warning";
    case "info":
      return "tw:alert-info";
  }
}

/**
 * Select the appropriate icon for the severity level.
 */
function SeverityIcon({ severity }: { severity: ErrorSeverity }) {
  switch (severity) {
    case "error":
      return <AlertTriangle size={20} className="tw:shrink-0" />;
    case "warning":
      return <AlertTriangle size={20} className="tw:shrink-0" />;
    case "info":
      return <Info size={20} className="tw:shrink-0" />;
  }
}

export function ErrorBanner({ error, onRetry, onDismiss, autoRecover }: ErrorBannerProps) {
  const severity = classifyError(error);
  const stableTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * Auto-recovery logic: poll health every 3 seconds. If healthy for 5+
   * consecutive seconds, dismiss the banner. If any check fails, reset
   * the timer. This prevents flicker on intermittent connectivity
   * (RESEARCH.md Pitfall 3).
   */
  useEffect(() => {
    if (!autoRecover || !onDismiss) return;

    const STABLE_DURATION_MS = 5_000;
    const CHECK_INTERVAL_MS = 3_000;

    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetchHealth();
        const healthy = res.status === "healthy" || res.status === "ok";

        if (healthy) {
          // Start the stability timer if not already running
          if (!stableTimerRef.current) {
            stableTimerRef.current = setTimeout(() => {
              onDismiss();
            }, STABLE_DURATION_MS);
          }
        } else {
          // Connection unstable -- reset stability timer
          if (stableTimerRef.current) {
            clearTimeout(stableTimerRef.current);
            stableTimerRef.current = null;
          }
        }
      } catch {
        // Health check failed -- reset stability timer
        if (stableTimerRef.current) {
          clearTimeout(stableTimerRef.current);
          stableTimerRef.current = null;
        }
      }
    }, CHECK_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (stableTimerRef.current) clearTimeout(stableTimerRef.current);
    };
  }, [autoRecover, onDismiss]);

  return (
    <div
      role="alert"
      className={`tw:alert ${alertClass(severity)} tw:mb-4`}
      data-testid="error-banner"
      data-severity={severity}
    >
      <SeverityIcon severity={severity} />
      <div className="tw:flex-1">
        <p className="tw:font-medium">{error.user_message}</p>
        {error.help_url && (
          <a
            href={error.help_url}
            target="_blank"
            rel="noopener noreferrer"
            className="tw:text-sm tw:underline tw:flex tw:items-center tw:gap-1 tw:mt-1"
          >
            Help <ExternalLink size={12} />
          </a>
        )}
        <ErrorDetail error={error} />
      </div>
      <div className="tw:flex tw:items-center tw:gap-1">
        {onRetry && (
          <button
            onClick={onRetry}
            className="tw:btn tw:btn-sm tw:btn-ghost"
            data-testid="error-retry-btn"
          >
            <RefreshCw size={14} /> Retry
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="tw:btn tw:btn-sm tw:btn-ghost tw:btn-square"
            aria-label="Dismiss error"
            data-testid="error-dismiss-btn"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
