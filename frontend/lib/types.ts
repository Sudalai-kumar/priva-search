/**
 * Shared TypeScript types for Priva-Search frontend.
 * All API response shapes are defined here — never use `any`.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Health
// ─────────────────────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: "ok" | "error";
  db: "ok" | "error";
  redis: "ok" | "error";
}

// ─────────────────────────────────────────────────────────────────────────────
// Brand
// ─────────────────────────────────────────────────────────────────────────────
export interface Brand {
  id: number;
  name: string;
  slug: string;
  domain: string | null;
  privacy_url: string | null;
  tier: 1 | 2;
  crawl_blocked: boolean;
  created_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Risk categories
// ─────────────────────────────────────────────────────────────────────────────
export type CategoryKey =
  | "data_selling"
  | "ai_training"
  | "third_party_sharing"
  | "data_retention"
  | "deceptive_ux";

export interface RiskCategory {
  category_key: CategoryKey;
  score: number;          // 1 (best) → 10 (worst)
  confidence: number;     // 0 → 100
  found: boolean;
  plain_summary: string;
  score_reason: string;
  risk_examples: string[];
  snippet: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Opt-out info
// ─────────────────────────────────────────────────────────────────────────────
export interface OptOutInfo {
  gpc_supported: boolean | null;
  do_not_sell_url: string | null;
  deletion_request_url: string | null;
  privacy_contact_email: string | null;
  opt_out_notes: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Scorecard
// ─────────────────────────────────────────────────────────────────────────────
export type TrustStatus = "verified" | "ai_generated" | "stale" | "needs_review";

export interface Scorecard {
  id: number;
  brand_id: number;
  overall_risk_score: number | null;
  overall_confidence: number | null;
  summary: string | null;
  trust_status: TrustStatus | null;
  last_scanned_at: string | null;
  model_used: string | null;
  crawl_method_used: string | null;
  legal_review_recommended: boolean;
  privacy_url: string | null;
  risk_categories: RiskCategory[];
  opt_out_info: OptOutInfo | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Scan job
// ─────────────────────────────────────────────────────────────────────────────
export type ScanStage =
  | "queued"
  | "discovery"
  | "crawling"
  | "analyzing"
  | "validating"
  | "done"
  | "failed";

export interface ScanProgressEvent {
  stage: ScanStage;
  message: string;
  progress: number;
  slug?: string;
}

export interface ScanJobStatus {
  scan_id: string;
  status: ScanStage;
  progress: number;
  error_message: string | null;
  slug: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Search response
// ─────────────────────────────────────────────────────────────────────────────
export interface SearchHit {
  brand: Brand;
  scorecard: Scorecard;
}

export interface SearchEnqueued {
  scan_id: string;
  captcha_required: boolean;
}

export type SearchResponse = SearchHit | SearchEnqueued;
