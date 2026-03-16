"use client";

import { use, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { fetchBrandScorecard } from "@/lib/api";
import { useScanSocket } from "@/lib/socket";
import ScanProgress from "@/components/ScanProgress";
import NutritionLabel from "@/components/NutritionLabel";
import OptOutButton from "@/components/OptOutButton";

interface PageProps {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ scan_id?: string }>;
}

export default function BrandPage({ params, searchParams }: PageProps) {
  const { slug } = use(params);
  const { scan_id: scanId } = use(searchParams);
  const router = useRouter();

  // 1. WebSocket-driven scan progress (auto-falls back to HTTP polling)
  const { stage, message, progress, slug: doneSlug } = useScanSocket(scanId ?? null);
  const isScanning = !!scanId && stage !== "done" && stage !== "failed";

  // 2. When the scan finishes, redirect to the clean URL and refetch
  useEffect(() => {
    if (stage === "done" && doneSlug) {
      router.replace(`/brand/${doneSlug}`);
    }
  }, [stage, doneSlug, router]);

  // 3. Fetch scorecard (only when not actively scanning)
  const { data: scorecard, isLoading, isError, refetch } = useQuery({
    queryKey: ["brand", slug],
    queryFn: () => fetchBrandScorecard(slug),
    enabled: !isScanning,
    retry: false,
  });

  // Re-fetch once scan signals done
  useEffect(() => {
    if (stage === "done") refetch();
  }, [stage, refetch]);

  // ── Render: Scanning in progress ──────────────────────────────────────────
  if (isScanning || (scanId && stage === null)) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-zinc-950 border border-zinc-800 p-8 rounded-3xl">
          <ScanProgress
            stage={stage ?? "queued"}
            message={message}
            progress={progress}
          />
        </div>
      </main>
    );
  }

  // ── Render: Loading scorecard ─────────────────────────────────────────────
  if (isLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-zinc-900 border-t-indigo-500 rounded-full animate-spin" />
          <p className="text-zinc-500 text-sm">Loading assessment…</p>
        </div>
      </main>
    );
  }

  // ── Render: Error / Not found ─────────────────────────────────────────────
  if (isError || !scorecard) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-4">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-2">Scorecard not found</h1>
          <p className="text-zinc-400">No results for &quot;{slug}&quot;.</p>
        </div>
        <button
          onClick={() => router.push("/")}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-xl"
        >
          Back to Search
        </button>
      </main>
    );
  }

  // ── Render: Scorecard ─────────────────────────────────────────────────────
  const brandName = slug.charAt(0).toUpperCase() + slug.slice(1);

  return (
    <main className="min-h-screen py-16 px-4 max-w-4xl mx-auto space-y-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center"
      >
        <NutritionLabel scorecard={scorecard} brandName={brandName} />
      </motion.div>

      {scorecard.opt_out_info && (
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="glass p-8 rounded-3xl flex flex-col md:flex-row items-center justify-between gap-6 overflow-hidden relative"
        >
          <div className="relative z-10">
            <h3 className="text-2xl font-bold mb-2">Take Action</h3>
            <p className="text-zinc-400 text-sm max-w-md">
              Send a request to opt-out or delete your data based on this policy.
            </p>
          </div>
          <OptOutButton brandName={brandName} optOutInfo={scorecard.opt_out_info} />
          <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-600/10 blur-3xl -z-0" />
        </motion.section>
      )}

      <footer className="pt-8 border-t border-zinc-900 flex flex-wrap gap-8 text-[10px] text-zinc-600 uppercase tracking-widest">
        <span>Last Scanned: {scorecard.last_scanned_at ? new Date(scorecard.last_scanned_at).toLocaleDateString() : "N/A"}</span>
        <span>Model: {scorecard.model_used}</span>
        <span>Method: {scorecard.crawl_method_used}</span>
        {scorecard.legal_review_recommended && (
          <span className="text-amber-600">⚠ Manual Review Recommended</span>
        )}
      </footer>
    </main>
  );
}
