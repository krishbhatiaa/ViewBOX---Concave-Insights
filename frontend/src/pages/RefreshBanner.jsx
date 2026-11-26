import { useState } from "react";

export default function RefreshBanner({ onRetry }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div
      role="alert"
      className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
    >
      <span>Couldn't refresh — showing cached data.</span>
      <div className="flex items-center gap-3">
        <button type="button" onClick={onRetry} className="min-h-11 font-semibold underline">
          Retry
        </button>
        <button
          type="button"
          aria-label="Dismiss refresh warning"
          onClick={() => setDismissed(true)}
          className="flex h-11 w-11 items-center justify-center rounded-lg text-lg leading-none"
        >
          ×
        </button>
      </div>
    </div>
  );
}
