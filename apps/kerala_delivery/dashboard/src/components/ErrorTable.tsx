/**
 * ErrorTable -- Inline error table for CSV upload failures.
 *
 * Displays failed import rows with row number, address, reason, and stage.
 * Provides two action buttons:
 * - "Download Error Report" -- generates a CSV of failures for offline review
 * - "Upload Fixed CSV" -- triggers the file input for re-upload
 *
 * Color-coded rows:
 * - Validation failures: red tint background
 * - Geocoding failures: amber tint background
 *
 * Capped at 50 visible rows with "... and N more" message to avoid
 * rendering performance issues with large failure sets.
 * See: .planning/phases/02-error-handling-infrastructure/02-RESEARCH.md Open Question 2
 */

import { Download, Upload } from "lucide-react";
import type { ImportFailure } from "../types";

/** Max rows to display before showing a "... and N more" truncation message. */
const MAX_DISPLAY_ROWS = 50;

interface ErrorTableProps {
  failures: ImportFailure[];
  /** Callback to download failures as a CSV file. */
  onDownloadReport?: () => void;
  /** Callback to trigger the file input for re-upload. */
  onReupload?: () => void;
}

/**
 * Generate a CSV blob from failures and trigger a browser download.
 */
function downloadFailuresAsCsv(failures: ImportFailure[]) {
  const header = "Row,Address,Reason,Stage";
  const rows = failures.map(
    (f) =>
      `${f.row_number},"${(f.address_snippet || "").replace(/"/g, '""')}","${f.reason.replace(/"/g, '""')}",${f.stage}`
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "error-report.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Row background color based on failure stage.
 * Validation failures get a subtle red tint, geocoding failures get amber.
 */
function rowBgClass(stage: string): string {
  if (stage === "validation") return "tw:bg-error/5";
  if (stage === "geocoding") return "tw:bg-warning/5";
  return "";
}

export function ErrorTable({ failures, onDownloadReport, onReupload }: ErrorTableProps) {
  if (!failures || failures.length === 0) return null;

  const displayRows = failures.slice(0, MAX_DISPLAY_ROWS);
  const remainingCount = failures.length - displayRows.length;

  const handleDownload = () => {
    if (onDownloadReport) {
      onDownloadReport();
    } else {
      downloadFailuresAsCsv(failures);
    }
  };

  return (
    <div className="tw:mt-4" data-testid="error-table-container">
      <div className="tw:overflow-x-auto">
        <table className="tw:table tw:table-sm" data-testid="error-table">
          <thead>
            <tr>
              <th>Row #</th>
              <th>Address</th>
              <th>Reason</th>
              <th>Stage</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((f, idx) => (
              <tr key={`err-${f.row_number}-${idx}`} className={rowBgClass(f.stage)}>
                <td className="tw:font-mono tw:text-xs">{f.row_number}</td>
                <td className="tw:max-w-48 tw:truncate">{f.address_snippet || "--"}</td>
                <td>{f.reason}</td>
                <td>
                  <span
                    className={`tw:badge tw:badge-xs ${
                      f.stage === "validation"
                        ? "tw:badge-error"
                        : "tw:badge-warning"
                    }`}
                  >
                    {f.stage}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {remainingCount > 0 && (
        <p className="tw:text-sm tw:text-base-content/60 tw:mt-2 tw:text-center">
          ... and {remainingCount} more error{remainingCount !== 1 ? "s" : ""}
        </p>
      )}

      {/* Action buttons */}
      <div className="tw:flex tw:gap-2 tw:mt-3">
        <button
          className="tw:btn tw:btn-sm tw:btn-outline"
          onClick={handleDownload}
          data-testid="error-download-btn"
        >
          <Download size={14} /> Download Error Report
        </button>
        {onReupload && (
          <button
            className="tw:btn tw:btn-sm tw:btn-primary"
            onClick={onReupload}
            data-testid="error-reupload-btn"
          >
            <Upload size={14} /> Upload Fixed CSV
          </button>
        )}
      </div>
    </div>
  );
}
