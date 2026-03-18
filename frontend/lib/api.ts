/**
 * API client — all REST calls to the FastAPI backend.
 * Uses native fetch (no axios per spec).
 * All functions are async and typed against lib/types.ts.
 */

import type {
  HealthResponse,
  Scorecard,
  ScanJobStatus,
  OptOutInfo,
  SearchResponse,
  SearchHit,
  SearchEnqueued,
} from "@/lib/types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      (body as { error?: string }).error ?? `HTTP ${res.status}`
    );
  }

  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Health
// ─────────────────────────────────────────────────────────────────────────────

/** Check backend health status. */
export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────

/** Search for a brand's scorecard. Returns cached data or a scan_id. */
export async function searchBrand(query: string): Promise<SearchResponse> {
  const data = await apiFetch<any>(
    `/search?q=${encodeURIComponent(query)}`
  );
  
  // If scan_id is present, it's a SearchEnqueued
  if (data.scan_id) {
    return {
      scan_id: data.scan_id,
      captcha_required: false,
    } as SearchEnqueued;
  }
  
  // Otherwise it's a Scorecard (SearchHit shape in frontend expects {brand, scorecard})
  // Our backend /search returns the Scorecard directly with brand attached
  return {
    brand: data.brand,
    scorecard: data,
  } as SearchHit;
}

// ─────────────────────────────────────────────────────────────────────────────
// Scan
// ─────────────────────────────────────────────────────────────────────────────

/** Enqueue a new scan job. Returns { scan_id: string }. */
export async function enqueueScan(
  brandName: string,
  domain?: string
): Promise<{ scan_id: string }> {
  return apiFetch<{ scan_id: string }>("/scan", {
    method: "POST",
    body: JSON.stringify({ brand_name: brandName, domain }),
  });
}

/** Poll scan job status (fallback when WebSocket unavailable). */
export async function fetchScanStatus(scanId: string): Promise<ScanJobStatus> {
  return apiFetch<ScanJobStatus>(`/scan/${scanId}/status`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Brand
// ─────────────────────────────────────────────────────────────────────────────

/** Fetch the full scorecard for a brand by slug. */
export async function fetchBrandScorecard(slug: string): Promise<Scorecard> {
  return apiFetch<Scorecard>(`/brand/${slug}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Opt-out
// ─────────────────────────────────────────────────────────────────────────────

/** Fetch opt-out info for a brand. */
export async function fetchOptOut(slug: string): Promise<OptOutInfo> {
  return apiFetch<OptOutInfo>(`/optout/${slug}`);
}
