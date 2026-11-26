import { useState } from "react";

export default function RefreshBanner({ onRetry }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div
      role="alert"
      className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-[2px] border border-l-4 border-line-2 border-l-acc bg-paper-3 px-4 py-3 text-sm text-ink-2"
    >
      <span className="font-mono text-xs uppercase tracking-wide text-acc">Refresh warning</span>
      <span className="flex-1">Couldn't refresh — showing cached data.</span>
      <div className="flex items-center gap-3">
        <button type="button" onClick={onRetry} className="min-h-11 font-mono text-xs font-semibold uppercase tracking-wide underline">
          Retry
        </button>
        <button
          type="button"
          aria-label="Dismiss refresh warning"
          onClick={() => setDismissed(true)}
          className="flex h-11 w-11 items-center justify-center rounded-[2px] text-xl leading-none text-ink-3 hover:text-ink"
        >
          ×
        </button>
      </div>
    </div>
  );
}
