"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RiskCategory as RiskCategoryType } from "@/lib/types";
import SnippetDrawer from "./SnippetDrawer";
import ScoreExplanation from "./ScoreExplanation";

const CATEGORY_LABELS: Record<string, string> = {
  data_selling: "Data Selling",
  ai_training: "AI Training",
  third_party_sharing: "Third-Party Sharing",
  data_retention: "Data Retention",
  deceptive_ux: "Deceptive UX",
};

interface RiskCategoryProps {
  category: RiskCategoryType;
  index: number;
}

/**
 * Individual expandable risk category row in the scorecard.
 * Clicking expands to show score_reason, risk_examples, and source snippet.
 */
export default function RiskCategory({ category, index }: RiskCategoryProps) {
  const [expanded, setExpanded] = useState(false);
  const { category_key, score, confidence, found, plain_summary, score_reason, risk_examples, snippet } =
    category;

  const scoreColor =
    score <= 3 ? "score-good" : score <= 6 ? "score-warn" : "score-danger";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      className="rounded-xl border border-zinc-800 hover:border-zinc-700 transition-colors overflow-hidden"
    >
      {/* Row header */}
      <button
        id={`risk-category-${category_key}`}
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 p-4 text-left cursor-pointer"
        aria-expanded={expanded}
      >
        <span className={`text-2xl font-black w-8 tabular-nums ${scoreColor}`}>
          {score}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-zinc-200">
            {CATEGORY_LABELS[category_key] ?? category_key}
          </p>
          <p className="text-xs text-zinc-500 truncate">{plain_summary}</p>
        </div>
        <svg
          className={`w-4 h-4 text-zinc-600 flex-shrink-0 transition-transform duration-200 ${
            expanded ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 flex flex-col gap-3 border-t border-zinc-800 pt-3">
              <ScoreExplanation
                scoreReason={score_reason}
                riskExamples={risk_examples}
                confidence={confidence}
              />
              {snippet && found && (
                <SnippetDrawer snippet={snippet} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
