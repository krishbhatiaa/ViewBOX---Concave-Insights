import { forwardRef, useState } from "react";

export const TONES = {
  emerald: "border-deep bg-deep/10 text-deep",
  rose: "border-acc bg-acc/10 text-acc",
  amber: "border-line-2 bg-paper-3 text-ink-2",
  sky: "border-line-2 bg-paper-3 text-ink-2",
  slate: "border-line bg-paper-3 text-ink-2",
  indigo: "border-deep bg-transparent text-deep",
  match: "border-acc-2/40 bg-acc-2/25 text-ink",
};

export const BAR_TONES = {
  sky: "bg-ink-3",
  amber: "bg-acc-2",
  emerald: "bg-deep",
};

export function Card({ className = "", children, ...rest }) {
  return (
    <section
      className={`rounded-[2px] border border-line bg-paper-2 p-4 sm:p-5 ${className}`}
      {...rest}
    >
      {children}
    </section>
  );
}

export function Button({ variant = "primary", className = "", type = "button", loading = false, disabled, children, ...rest }) {
  const base =
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-[2px] border px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-60";
  const styles = {
    primary:
      "border-[#c43518] bg-[#c43518] text-paper hover:bg-[#a52d12] active:bg-[#8e2510] dark:border-acc dark:bg-acc dark:text-ink dark:hover:bg-acc-2",
    secondary:
      "border-line-2 bg-paper text-ink hover:bg-paper-2 active:bg-paper-3",
    ghost: "border-transparent bg-transparent text-acc hover:bg-paper-2",
    danger:
      "border-[#c43518] bg-[#c43518] text-paper hover:bg-[#a52d12] active:bg-[#8e2510] dark:border-acc dark:bg-acc dark:text-ink dark:hover:bg-acc-2",
  };
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`${base} ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && (
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
          <path d="M4 12a8 8 0 0 1 8-8" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
        </svg>
      )}
      {children}
    </button>
  );
}

const inputCls =
  "min-h-11 w-full rounded-[2px] border border-line-2 bg-paper px-3 py-2 font-mono text-sm text-ink placeholder:text-ink-3 focus:border-acc focus:outline-none focus:ring-1 focus:ring-acc";

export function Field({ label, error, hint, required, children, id }) {
  return (
    <label htmlFor={id} className="block text-sm font-medium text-ink-2">
      <span className="mb-1 block font-mono text-xs uppercase tracking-wide text-ink-3">
        {label}
        {required && <span className="text-acc"> *</span>}
      </span>
      {children}
      {hint && !error && <span className="mt-1 block font-mono text-xs font-normal text-ink-3">{hint}</span>}
      {error && (
        <span role="alert" className="mt-1 block font-mono text-xs font-normal text-acc">
          {error}
        </span>
      )}
    </label>
  );
}

export const Input = forwardRef(function Input({ error, className = "", ...rest }, ref) {
  return <input ref={ref} aria-invalid={!!error || undefined} className={`${inputCls} ${error ? "border-acc" : ""} ${className}`} {...rest} />;
});

export function Select({ error, className = "", children, ...rest }) {
  return (
    <select aria-invalid={!!error || undefined} className={`${inputCls} ${error ? "border-acc" : ""} ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Textarea({ error, className = "", ...rest }) {
  return (
    <textarea
      aria-invalid={!!error || undefined}
      className={`${inputCls} min-h-24 ${error ? "border-acc" : ""} ${className}`}
      {...rest}
    />
  );
}

export function Tag({ tone = "slate", className = "", children }) {
  return (
    <span
      className={`inline-flex items-center rounded-[2px] border px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wide ${TONES[tone] || TONES.slate} ${className}`}
    >
      {children}
    </span>
  );
}

export function StageTag({ stage }) {
  const tone =
    stage === "Approved" || stage === "Completed" || stage === "Paid"
      ? "emerald"
      : stage === "Rejected" || stage === "Failed"
        ? "rose"
        : stage === "Waitlisted" || stage === "Fit" || stage === "Pending" || stage === "Lead"
          ? "amber"
          : stage === "Approved by ops"
            ? "indigo"
            : "slate";
  return <Tag tone={tone}>{stage}</Tag>;
}

export function Skeleton({ className = "" }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-[2px] bg-paper-3 ${className}`} />;
}

export function LoadingCard({ label = "Loading…" }) {
  return (
    <Card aria-busy="true" aria-label={label}>
      <div className="space-y-3">
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
      <span className="sr-only">{label}</span>
    </Card>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <Card className="text-center">
      <svg
        width="36"
        height="36"
        viewBox="0 0 36 36"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden="true"
        className="mx-auto mb-3 text-ink-2"
      >
        <rect x="6" y="5" width="24" height="26" />
        <path d="M11 12h14M11 18h10M11 24h6" />
      </svg>
      <p className="font-display text-xl font-normal text-ink">{title}</p>
      {description && <p className="mt-1 text-sm text-ink-2">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <Card role="alert" className="border-acc bg-acc/5">
      <div className="flex items-start gap-3">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
          className="mt-0.5 shrink-0 text-acc"
        >
          <path d="M10 14 14 10M8.5 15.5l-2 2a3.5 3.5 0 0 1-5-5l2-2M15.5 8.5l2-2a3.5 3.5 0 0 1 5 5l-2 2" />
        </svg>
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-wide text-acc">Error</p>
          <p className="mt-1 text-sm text-ink">{message}</p>
          {onRetry && (
            <div className="mt-3">
              <Button variant="secondary" onClick={onRetry}>
                Try again
              </Button>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

export function InlineError({ message }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-[2px] border border-l-4 border-acc bg-acc/5 px-3 py-2 font-mono text-xs text-ink">
      <span className="font-semibold uppercase tracking-wide text-acc">Error · </span>
      {message}
    </p>
  );
}

export function CopyButton({ value, label = "Copy", className = "", onCopied }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = value;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setCopied(true);
    onCopied?.();
    setTimeout(() => setCopied(false), 1800);
  }
  return (
    <Button variant="secondary" className={className} onClick={copy} aria-label={copied ? "Copied" : label}>
      {copied ? "Copied!" : label}
    </Button>
  );
}

export function Table({ children, className = "" }) {
  return (
    <div className={`-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0 ${className}`}>
      <table className="w-full min-w-max border-collapse text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children }) {
  return (
    <th className="sticky top-0 border-b border-line-2 bg-paper-2 px-3 py-2.5 font-mono text-xs font-semibold uppercase tracking-wide text-ink-3">
      {children}
    </th>
  );
}

export function Td({ children, className = "" }) {
  return <td className={`border-b border-line px-3 py-2.5 ${className}`}>{children}</td>;
}

export function PageHeader({ kicker, title, description, actions }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-ink pb-4">
      <div>
        {kicker && <p className="mb-1 font-mono text-[11px] uppercase tracking-[.08em] text-acc">{kicker}</p>}
        <h1 className="font-display text-3xl font-normal tracking-tight sm:text-5xl">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function AuthShell({ eyebrow, title, description, children, footer }) {
  return (
    <div className="viewbox-enter mx-auto grid min-h-dvh max-w-6xl gap-8 px-4 py-10 lg:grid-cols-[1.1fr_.9fr] lg:items-center lg:py-16">
      <section>
        <p className="font-mono text-[11px] uppercase tracking-[.08em] text-acc">{eyebrow}</p>
        <h1 className="mt-3 font-display text-4xl leading-none tracking-tight sm:text-6xl">{title}</h1>
        <p className="mt-4 max-w-md text-sm text-ink-2">{description}</p>
        <div className="mt-8 flex items-center gap-4">
          <svg
            viewBox="0 0 120 120"
            className="viewbox-spin-slow h-28 w-28 shrink-0"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="60" cy="60" r="52" stroke="var(--color-ink)" strokeWidth="1" strokeDasharray="6 6" />
            <circle cx="60" cy="60" r="38" stroke="var(--color-acc)" strokeWidth="1.5" strokeDasharray="48 18 14 18" />
            <circle cx="60" cy="60" r="24" stroke="var(--color-ink)" strokeWidth="1.25" strokeDasharray="30 12" />
            <circle cx="60" cy="60" r="9" stroke="var(--color-acc)" strokeWidth="1.5" />
          </svg>
          <p className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">
            ViewBOX / Research Panel
          </p>
        </div>
      </section>
      <section>
        {children}
        {footer && <div className="mt-4">{footer}</div>}
      </section>
    </div>
  );
}

export function StatCard({ label, value, tone = "slate", delta }) {
  const colors = {
    emerald: "border-l-deep",
    amber: "border-l-ink-3",
    rose: "border-l-acc",
    slate: "border-l-line-2",
    indigo: "border-l-deep",
    sky: "border-l-ink-3",
  };
  return (
    <Card className={`!p-4 border-t-2 border-t-ink border-l-4 ${colors[tone] || colors.slate}`}>
      <p className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">{label}</p>
      <p className="mt-1 font-display text-4xl font-normal tabular-nums text-ink">{value}</p>
      {delta && <p className="mt-1 font-mono text-xs text-deep">{delta}</p>}
    </Card>
  );
}
