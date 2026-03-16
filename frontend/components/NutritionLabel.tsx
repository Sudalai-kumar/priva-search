"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { Scorecard } from "@/lib/types";
import RiskCategory from "./RiskCategory";
import TrustBadge from "./TrustBadge";

interface NutritionLabelProps {
  scorecard: Scorecard;
  brandName: string;
}

/**
 * The 5-category privacy scorecard card — styled like a nutrition label.
 * Displays overall score, trust badge, and each risk category row.
 */
export default function NutritionLabel({
  scorecard,
  brandName,
}: NutritionLabelProps) {
  const { overall_risk_score, trust_status, summary, risk_categories } =
    scorecard;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass p-6 rounded-2xl w-full max-w-xl"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold">{brandName}</h2>
          {summary && (
            <p className="text-sm text-zinc-400 mt-1 leading-relaxed">{summary}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {trust_status && <TrustBadge status={trust_status} />}
          {overall_risk_score !== null && (
            <div
              className={`text-4xl font-black tabular-nums ${
                overall_risk_score <= 3
                  ? "score-good"
                  : overall_risk_score <= 6
                  ? "score-warn"
                  : "score-danger"
              }`}
            >
              {overall_risk_score}
              <span className="text-base font-normal text-zinc-500">/10</span>
            </div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-zinc-800 mb-4" />

      {/* Risk category rows */}
      <div className="flex flex-col gap-2">
        <AnimatePresence>
          {risk_categories.map((cat, i) => (
            <RiskCategory key={cat.category_key} category={cat} index={i} />
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
