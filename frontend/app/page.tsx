"use client";

import { motion, type Variants } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";
import SearchBar from "@/components/SearchBar";

// Animation variants
const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.55, ease: [0.25, 0.46, 0.45, 0.94] },
  }),
};

export default function HomePage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: 3,
  });

  const backendOnline = health?.status === "ok";

  return (
    <main className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-4 py-16">
      {/* ── Background blobs ── */}
      <div
        aria-hidden="true"
        className="blob absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full opacity-20"
        style={{
          background:
            "radial-gradient(circle at center, #6366f1 0%, transparent 70%)",
        }}
      />
      <div
        aria-hidden="true"
        className="blob blob-delay absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full opacity-15"
        style={{
          background:
            "radial-gradient(circle at center, #a78bfa 0%, transparent 70%)",
        }}
      />

      {/* ── Backend status badge ── */}
      <motion.div
        custom={0}
        initial="hidden"
        animate="visible"
        variants={fadeUp}
        className="mb-10 flex items-center gap-2"
      >
        {healthLoading ? (
          <span className="text-xs text-zinc-500 tracking-wide">
            Checking backend…
          </span>
        ) : (
          <span
            id="backend-status-badge"
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
              backendOnline
                ? "bg-green-950/60 border-green-800 text-green-400"
                : "bg-red-950/60 border-red-800 text-red-400"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                backendOnline ? "bg-green-400" : "bg-red-400"
              }`}
            />
            {backendOnline ? "Backend online" : "Backend offline"}
            {health && (
              <span className="ml-1 opacity-60">
                · DB {health.db} · Redis {health.redis}
              </span>
            )}
          </span>
        )}
      </motion.div>

      {/* ── Hero heading ── */}
      <motion.div
        custom={1}
        initial="hidden"
        animate="visible"
        variants={fadeUp}
        className="text-center mb-4"
      >
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-none mb-4">
          <span className="gradient-text">Privacy</span> Scorecard
        </h1>
        <p className="text-zinc-400 text-lg sm:text-xl max-w-xl mx-auto leading-relaxed">
          Paste any privacy policy URL and instantly know how they handle your personal data — powered by AI analysis.
        </p>
      </motion.div>

      {/* ── Search bar ── */}
      <motion.div
        custom={2}
        initial="hidden"
        animate="visible"
        variants={fadeUp}
        className="w-full max-w-2xl mt-8"
      >
        <SearchBar />
      </motion.div>

      {/* ── Feature pills ── */}
      <motion.div
        custom={3}
        initial="hidden"
        animate="visible"
        variants={fadeUp}
        className="mt-12 flex flex-wrap justify-center gap-3"
      >
        {[
          { icon: "🔍", label: "5 Risk Categories" },
          { icon: "⚡", label: "Instant Results" },
          { icon: "🤖", label: "AI-Powered" },
          { icon: "🔒", label: "No Tracking" },
          { icon: "✅", label: "Opt-Out Links" },
        ].map(({ icon, label }) => (
          <span
            key={label}
            className="glass px-4 py-2 rounded-full text-sm text-zinc-300 flex items-center gap-2"
          >
            <span>{icon}</span>
            {label}
          </span>
        ))}
      </motion.div>

      {/* ── Category preview strip ── */}
      <motion.div
        custom={4}
        initial="hidden"
        animate="visible"
        variants={fadeUp}
        className="mt-16 grid grid-cols-2 sm:grid-cols-5 gap-3 w-full max-w-3xl"
      >
        {[
          { key: "Data Selling", emoji: "💰" },
          { key: "AI Training", emoji: "🤖" },
          { key: "3rd Party Sharing", emoji: "📡" },
          { key: "Data Retention", emoji: "🗄️" },
          { key: "Deceptive UX", emoji: "🎭" },
        ].map(({ key, emoji }) => (
          <div
            key={key}
            className="glass p-3 rounded-xl flex flex-col items-center gap-2 text-center hover:border-indigo-800 transition-colors duration-200"
          >
            <span className="text-2xl">{emoji}</span>
            <span className="text-xs text-zinc-400 leading-snug">{key}</span>
          </div>
        ))}
      </motion.div>
    </main>
  );
}
