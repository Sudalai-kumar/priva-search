"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

interface SearchBarProps {
  placeholder?: string;
}

/**
 * Main search input component.
 * Navigates to /brand/{slug} on submit.
 * Shows a loading spinner while navigating.
 */
export default function SearchBar({
  placeholder = "Paste a privacy policy URL (e.g., https://example.com/privacy)...",
}: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    let trimmed = query.trim();
    if (!trimmed) return;

    // Basic URL validation/auto-fix
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
      trimmed = "https://" + trimmed;
    }

    try {
      new URL(trimmed);
    } catch {
      alert("Please enter a valid URL.");
      return;
    }

    setLoading(true);
    try {
      const { searchBrand } = await import("@/lib/api");
      const result = await searchBrand(trimmed);

      if ("scorecard" in result) {
        // Cached hit
        router.push(`/brand/${result.brand.slug}`);
      } else {
        // Enqueued scan
        // Extract domain from URL to act as fallback slug if needed during routing
        const urlObj = new URL(trimmed);
        let fallbackSlug = urlObj.hostname.replace(/^www\./, "");
        fallbackSlug = fallbackSlug.replace(/\./g, "-").toLowerCase();
        
        router.push(`/brand/${fallbackSlug}?scan_id=${result.scan_id}`);
      }
    } catch (err) {
      console.error("Search failed:", err);
      // Fallback to direct navigation
      const urlObj = new URL(trimmed);
      let fallbackSlug = urlObj.hostname.replace(/^www\./, "");
      fallbackSlug = fallbackSlug.replace(/\./g, "-").toLowerCase();
      
      router.push(`/brand/${fallbackSlug}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="glow-ring flex items-center gap-3 bg-[#18181b] rounded-2xl px-5 py-4 w-full"
      role="search"
      aria-label="Search brands"
    >
      {/* Search icon */}
      <svg
        aria-hidden="true"
        className="w-5 h-5 text-zinc-500 flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"
        />
      </svg>

      <input
        ref={inputRef}
        id="brand-search-input"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-transparent text-zinc-100 placeholder-zinc-600 text-base outline-none min-w-0"
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        disabled={loading}
      />

      {/* Submit button */}
      <motion.button
        id="brand-search-submit"
        type="submit"
        disabled={loading || !query.trim()}
        whileTap={{ scale: 0.96 }}
        className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 disabled:text-indigo-600
                   text-white text-sm font-semibold px-5 py-2.5 rounded-xl
                   transition-colors duration-150 flex-shrink-0 flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Analyzing URL…
          </>
        ) : (
          "Analyze"
        )}
      </motion.button>
    </form>
  );
}
