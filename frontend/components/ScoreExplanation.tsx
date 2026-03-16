interface ScoreExplanationProps {
  scoreReason: string;
  riskExamples: string[];
  confidence: number;
}

/**
 * Displays the score_reason and risk_examples for a risk category.
 * Shown inside the expanded RiskCategory drawer.
 */
export default function ScoreExplanation({
  scoreReason,
  riskExamples,
  confidence,
}: ScoreExplanationProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Score reason */}
      <p className="text-sm text-zinc-300 leading-relaxed font-medium">
        {scoreReason}
      </p>

      {/* Risk examples / Evidence */}
      {riskExamples.length > 0 && (
        <div className="flex flex-col gap-2 bg-zinc-900/50 p-3 rounded-lg border border-zinc-800/50">
          <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
            <span className="w-1 h-1 bg-indigo-500 rounded-full" />
            Decision Context & Evidence
          </p>
          <ul className="flex flex-col gap-2">
            {riskExamples.map((example, i) => (
              <li key={i} className="flex gap-2 text-[13px] text-zinc-400 italic leading-relaxed pl-3 border-l-2 border-zinc-800">
                {example.length > 40 ? `"${example.replace(/^"|"$/g, '')}"` : example}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence indicator */}
      <div className="flex items-center gap-2 mt-1">
        <span className="text-[11px] font-semibold text-zinc-600 uppercase tracking-wider">AI Confidence</span>
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className={`w-3.5 h-1.5 rounded-sm transition-colors duration-500 ${
                i < Math.round(confidence / 20)
                  ? "bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.4)]"
                  : "bg-zinc-800"
              }`}
            />
          ))}
        </div>
        <span className="text-xs font-medium text-zinc-500 ml-1">{confidence}%</span>
      </div>
    </div>
  );
}
