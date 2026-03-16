"use client";

import { motion } from "framer-motion";
import type { ScanStage } from "@/lib/types";

interface ScanProgressProps {
  stage: ScanStage;
  message: string;
  progress: number;
}

const STAGE_LABELS: Record<ScanStage, string> = {
  queued: "In queue",
  discovery: "Finding privacy policy URL",
  crawling: "Reading privacy policy",
  analyzing: "AI is analyzing the policy",
  validating: "Verifying results",
  done: "Scan complete",
  failed: "Scan failed",
};

/**
 * WebSocket-driven live progress bar shown during an active scan.
 * Reads progress events from the useScanSocket hook and renders
 * an animated progress bar + stage label.
 */
export default function ScanProgress({ stage, message, progress }: ScanProgressProps) {
  const isError = stage === "failed";
  const isDone = stage === "done";

  return (
    <div
      id="scan-progress"
      role="progressbar"
      aria-valuenow={progress}
      aria-valuemin={0}
      aria-valuemax={100}
      className="w-full max-w-xl"
    >
      <div className="flex justify-between items-center mb-2">
        <p className="text-sm font-medium text-zinc-300">
          {message || STAGE_LABELS[stage]}
        </p>
        <span
          className={`text-sm font-bold tabular-nums ${
            isError ? "text-red-400" : isDone ? "text-green-400" : "text-indigo-400"
          }`}
        >
          {progress}%
        </span>
      </div>

      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${
            isError
              ? "bg-red-500"
              : isDone
              ? "bg-green-500"
              : "bg-gradient-to-r from-indigo-600 to-violet-500"
          }`}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      </div>

      {isError && (
        <p className="text-xs text-red-400 mt-2">
          Something went wrong. Please try again.
        </p>
      )}
    </div>
  );
}
