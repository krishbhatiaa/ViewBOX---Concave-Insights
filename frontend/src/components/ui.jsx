import { useState } from "react";

const TONES = {
  emerald: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  rose: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  amber: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
  sky: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  slate: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  indigo: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
};

export function Card({ className = "", children, ...rest }) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-5 ${className}`}
      {...rest}
    >
      {children}
    </section>
  );
}

export function Button({ variant = "primary", className = "", type = "button", loading = false, disabled, children, ...rest }) {
  const base =
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60";
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800",
    secondary:
      "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
    ghost: "text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-950",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
  };
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`${base} ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
          <path d="M4 12a8 8 0 0 1 8-8" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
        </svg>
      )}
      {children}
    </button>
  );
}

const inputCls =
  "min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-indigo-900";

export function Field({ label, error, hint, required, children, id }) {
  return (
    <label htmlFor={id} className="block text-sm font-medium">
      <span className="mb-1 block text-slate-700 dark:text-slate-300">
        {label}
        {required && <span className="text-rose-600 dark:text-rose-400"> *</span>}
      </span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span>}
      {error && (
        <span role="alert" className="mt-1 block text-xs font-normal text-rose-600 dark:text-rose-400">
          {error}
        </span>
      )}
    </label>
  );
}

export function Input({ error, className = "", ...rest }) {
  return <input aria-invalid={!!error || undefined} className={`${inputCls} ${error ? "border-rose-400" : ""} ${className}`} {...rest} />;
}

export function Select({ error, className = "", children, ...rest }) {
  return (
    <select aria-invalid={!!error || undefined} className={`${inputCls} ${error ? "border-rose-400" : ""} ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Textarea({ error, className = "", ...rest }) {
  return (
    <textarea
      aria-invalid={!!error || undefined}
      className={`${inputCls} min-h-24 ${error ? "border-rose-400" : ""} ${className}`}
      {...rest}
    />
  );
}

export function Tag({ tone = "slate", className = "", children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone] || TONES.slate} ${className}`}
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
        : stage === "Waitlisted" || stage === "Fit" || stage === "Pending"
          ? "amber"
          : stage === "Lead"
            ? "sky"
            : stage === "Approved" || stage === "Approved by ops"
              ? "indigo"
              : "slate";
  return <Tag tone={tone}>{stage}</Tag>;
}

export function Skeleton({ className = "" }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-slate-200 dark:bg-slate-800 ${className}`} />;
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
      <p className="font-medium text-slate-600 dark:text-slate-300">{title}</p>
      {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </Card>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <Card role="alert" className="border-rose-200 dark:border-rose-900">
      <p className="text-sm font-medium text-rose-700 dark:text-rose-300">{message}</p>
      {onRetry && (
        <div className="mt-3">
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </Card>
  );
}

export function InlineError({ message }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
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
    <th className="sticky top-0 border-b border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
      {children}
    </th>
  );
}

export function Td({ children, className = "" }) {
  return <td className={`border-b border-slate-100 px-3 py-2.5 dark:border-slate-800 ${className}`}>{children}</td>;
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, tone = "slate" }) {
  const colors = {
    emerald: "border-emerald-200 dark:border-emerald-900",
    amber: "border-amber-200 dark:border-amber-900",
    rose: "border-rose-200 dark:border-rose-900",
    slate: "border-slate-200 dark:border-slate-800",
    indigo: "border-indigo-200 dark:border-indigo-900",
  };
  return (
    <Card className={`!p-4 ${colors[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </Card>
  );
}
