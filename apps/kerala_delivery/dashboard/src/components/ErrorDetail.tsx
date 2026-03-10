/**
 * ErrorDetail -- Collapsible technical details panel for API errors.
 *
 * Renders inside an ErrorBanner to show the error_code, request_id,
 * timestamp, and technical_message when the user clicks "Show details".
 *
 * Uses DaisyUI collapse component (not custom state + CSS) to maintain
 * consistency with the existing ImportSummary collapse pattern.
 *
 * Why collapse instead of a modal: keeps the error context visible --
 * the user can see both the error message and the details simultaneously.
 * See: .planning/phases/02-error-handling-infrastructure/02-RESEARCH.md
 */

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ApiError } from "../lib/errors";

interface ErrorDetailProps {
  error: ApiError;
}

export function ErrorDetail({ error }: ErrorDetailProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="tw:collapse tw:mt-2" data-testid="error-detail">
      <input
        type="checkbox"
        checked={open}
        onChange={() => setOpen(!open)}
      />
      <div className="tw:collapse-title tw:text-xs tw:p-0 tw:min-h-0">
        <button
          onClick={(e) => {
            e.preventDefault();
            setOpen(!open);
          }}
          className="tw:text-xs tw:opacity-70 tw:flex tw:items-center tw:gap-1 tw:cursor-pointer"
          data-testid="error-detail-toggle"
        >
          {open ? "Hide details" : "Show details"}{" "}
          <ChevronDown
            size={12}
            className={`tw:transition-transform tw:duration-200 ${open ? "tw:rotate-180" : ""}`}
          />
        </button>
      </div>
      <div className="tw:collapse-content tw:text-xs tw:p-0">
        <div className="tw:mt-1 tw:space-y-1 tw:opacity-70">
          <p>Error: {error.error_code}</p>
          <p>Request ID: {error.request_id || "N/A"}</p>
          <p>Time: {error.timestamp ? new Date(error.timestamp).toLocaleTimeString() : "N/A"}</p>
          {error.technical_message && (
            <p>Detail: {error.technical_message}</p>
          )}
        </div>
      </div>
    </div>
  );
}
