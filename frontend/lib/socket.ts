/**
 * WebSocket client for scan progress.
 *
 * Uses native browser WebSocket (not socket.io per spec).
 * Falls back to polling via /scan/{scan_id}/status if WebSocket fails.
 */

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { ScanProgressEvent, ScanStage } from "@/lib/types";
import { fetchScanStatus } from "@/lib/api";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

const POLL_INTERVAL_MS = 2000;

interface UseScanSocketReturn {
  stage: ScanStage | null;
  message: string;
  progress: number;
  slug: string | null;
  error: string | null;
}

/**
 * Custom hook that connects to WS /ws/scan/{scanId} and streams progress events.
 * Automatically falls back to polling if the WebSocket connection fails.
 *
 * @param scanId - The UUID of the scan job, or null if no scan is active.
 */
export function useScanSocket(scanId: string | null): UseScanSocketReturn {
  const [stage, setStage] = useState<ScanStage | null>(null);
  const [message, setMessage] = useState<string>("");
  const [progress, setProgress] = useState<number>(0);
  const [slug, setSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const applyEvent = useCallback((evt: ScanProgressEvent) => {
    setStage(evt.stage);
    setMessage(evt.message);
    setProgress(evt.progress);
    if (evt.slug) setSlug(evt.slug);
  }, []);

  const startPolling = useCallback(
    (id: string) => {
      if (pollRef.current) return;
      pollRef.current = setInterval(async () => {
        try {
          const status = await fetchScanStatus(id);
          applyEvent({
            stage: status.status,
            message: status.status,
            progress: status.progress,
            slug: status.slug ?? undefined,
          });
          if (status.status === "done" || status.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch {
          // Silently retry
        }
      }, POLL_INTERVAL_MS);
    },
    [applyEvent]
  );

  useEffect(() => {
    if (!scanId) return;

    // Clean up previous connections
    if (wsRef.current) wsRef.current.close();
    if (pollRef.current) clearInterval(pollRef.current);

    const ws = new WebSocket(`${WS_URL}/ws/scan/${scanId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data as string) as ScanProgressEvent;
        applyEvent(evt);
        if (evt.stage === "done" || evt.stage === "failed") ws.close();
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onerror = () => {
      // WebSocket failed — fall back to polling
      setError(null); // not a user-visible error, just internal fallback
      startPolling(scanId);
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      ws.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [scanId, applyEvent, startPolling]);

  return { stage, message, progress, slug, error };
}
