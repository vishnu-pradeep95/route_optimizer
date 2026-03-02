/**
 * EmptyState -- meaningful empty state displayed when a page has no data.
 *
 * Per CONTEXT.md: lucide icon + descriptive message + primary action button.
 * Uses DaisyUI Tailwind classes with tw- prefix for consistent styling.
 *
 * Usage:
 *   <EmptyState
 *     icon={Truck}
 *     title="No vehicles yet"
 *     description="Add a vehicle to start assigning delivery routes."
 *     actionLabel="Add Vehicle"
 *     onAction={() => setShowAddForm(true)}
 *   />
 */
import type React from "react";

interface EmptyStateProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="tw-flex tw-flex-col tw-items-center tw-justify-center tw-py-16 tw-text-center">
      <Icon size={48} className="tw-text-base-content/30" />
      <h3 className="tw-text-lg tw-font-semibold tw-text-base-content/70 tw-mt-4">
        {title}
      </h3>
      <p className="tw-text-sm tw-text-base-content/50 tw-mt-1 tw-max-w-sm">
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          type="button"
          className="tw-btn tw-btn-primary tw-mt-4"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
