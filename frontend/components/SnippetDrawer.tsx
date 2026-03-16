"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface SnippetDrawerProps {
  snippet: string;
}

/**
 * Source-text reveal panel — shows the verbatim policy snippet
 * that the AI used to produce a category score.
 */
export default function SnippetDrawer({ snippet }: SnippetDrawerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        id="snippet-drawer-toggle"
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0121 9.414V19a2 2 0 01-2 2z" />
        </svg>
        {open ? "Hide source" : "View source text"}
      </button>

      <AnimatePresence>
        {open && (
          <motion.blockquote
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="mt-2 border-l-2 border-indigo-700 pl-3 text-xs text-zinc-400 italic leading-relaxed"
          >
            &ldquo;{snippet}&rdquo;
          </motion.blockquote>
        )}
      </AnimatePresence>
    </div>
  );
}
