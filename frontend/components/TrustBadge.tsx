import type { TrustStatus } from "@/lib/types";

interface TrustBadgeProps {
  status: TrustStatus;
}

const BADGE_CONFIG: Record<
  TrustStatus,
  { label: string; className: string; icon: string }
> = {
  verified: {
    label: "Verified",
    icon: "✓",
    className: "bg-green-950/60 border-green-800 text-green-400",
  },
  ai_generated: {
    label: "AI-Generated",
    icon: "🤖",
    className: "bg-amber-950/60 border-amber-800 text-amber-400",
  },
  stale: {
    label: "Stale",
    icon: "⚠",
    className: "bg-orange-950/60 border-orange-800 text-orange-400",
  },
  needs_review: {
    label: "Needs Review",
    icon: "⚑",
    className: "bg-red-950/60 border-red-800 text-red-400",
  },
};

/**
 * Displays a trust/freshness badge on the scorecard:
 * - Verified (green): Tier 1 curated brand, manually reviewed
 * - AI-Generated (amber): Tier 2 live scan result — not verified
 * - Stale (orange): Policy not re-scanned within 60 days
 * - Needs Review (red): Low confidence score detected
 */
export default function TrustBadge({ status }: TrustBadgeProps) {
  const config = BADGE_CONFIG[status];
  return (
    <span
      id={`trust-badge-${status}`}
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.className}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.label}
    </span>
  );
}
