import { useCallback, useEffect, useState } from "react";
import { api, sheetsPush, sheetsStatus } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingCard,
  PageHeader,
  StatCard,
  Table,
  Td,
  Th,
} from "../../components/ui.jsx";

export function FunnelBars({ items, max }) {
  const width = 120;
  const barH = 8;
  const gap = 4;
  const height = items.length * barH + (items.length - 1) * gap + 4;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible" aria-hidden="true">
      <line x1="0" y1="0" x2="0" y2={height} stroke="var(--color-line-2)" strokeWidth="1" />
      {items.map((item, i) => {
        const y = i * (barH + gap) + 2;
        const w = max > 0 ? Math.max((item.value / max) * (width - 8), item.value > 0 ? 3 : 0) : 0;
        return <rect key={item.label} x="1" y={y} width={w} height={barH} fill={item.color} />;
      })}
    </svg>
  );
}

function FunnelBar({ value, max, color }) {
  const width = 104;
  const w = max > 0 ? Math.max((value / max) * width, value > 0 ? 3 : 0) : 0;
  return (
    <div className="flex items-center gap-2">
      <svg width={width} height="12" viewBox={`0 0 ${width} 12`} aria-hidden="true" className="shrink-0">
        <line x1="0" y1="0" x2="0" y2="12" stroke="var(--color-line-2)" strokeWidth="1" />
        <line x1="0" y1="11.5" x2={width} y2="11.5" stroke="var(--color-line)" strokeWidth="1" />
        <rect x="1" y="2" width={w} height="7" fill={color} />
      </svg>
      <span className="font-mono text-xs font-medium tabular-nums text-ink">{value}</span>
    </div>
  );
}

function QualityBar({ rate, fill }) {
  const width = 92;
  const w = Math.max(0, Math.min(1, rate)) * width;
  return (
    <div className="flex items-center gap-2">
      <svg width={width} height="12" viewBox={`0 0 ${width} 12`} aria-hidden="true" className="shrink-0">
        <line x1="0" y1="0" x2="0" y2="12" stroke="var(--color-line-2)" strokeWidth="1" />
        <line x1="0" y1="11.5" x2={width} y2="11.5" stroke="var(--color-line)" strokeWidth="1" />
        <rect x="1" y="2" width={w} height="7" fill={fill} />
      </svg>
      <span className="font-mono text-xs font-medium tabular-nums text-ink">{Math.round(rate * 100)}%</span>
    </div>
  );
}

function relativeTime(iso) {
  if (!iso) return "never";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export default function StatsPage() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api("/api/admin/source-stats", { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSheet = useCallback(async () => {
    try {
      setSheet(await sheetsStatus());
    } catch (err) {
      setSheet({ status: "error", error: err.message, row_count: 0 });
    }
  }, []);

  const syncNow = async () => {
    setSyncing(true);
    try {
      let filters = {};
      try {
        filters = JSON.parse(sessionStorage.getItem("vb_grid_filters") || "{}");
      } catch {
        filters = {};
      }
      const result = await sheetsPush(filters);
      toast(`Synced ${result.rows} rows to ${result.sheet}`, "success");
      await loadSheet();
    } catch (err) {
      toast(`Sync failed: ${err.message}`, "error");
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    load();
    loadSheet();
  }, [load, loadSheet]);

  const max = rows ? Math.max(...rows.map((r) => r.signups), 1) : 1;
  const totals = rows
    ? rows.reduce((a, r) => ({ signups: a.signups + r.signups, fit: a.fit + r.fit, completed: a.completed + r.completed }), {
        signups: 0,
        fit: 0,
        completed: 0,
      })
    : null;

  const rated = rows ? rows.filter((r) => r.signups > 0) : [];
  const best = rated.reduce((a, b) => (!a || b.completion_rate > a.completion_rate ? b : a), null);
  const worst = rated.reduce((a, b) => (!a || b.completion_rate < a.completion_rate ? b : a), null);
  const ratio = best && worst
    ? worst.completion_rate > 0 ? (best.completion_rate / worst.completion_rate).toFixed(1) : "∞"
    : null;

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="ADMIN / 05"
        title="Source dashboard"
        description="Sign-ups, Fit and Completed per channel — sorted by volume."
      />

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

      <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">Google Sheets</h2>
          <p className="mt-1 font-mono text-xs text-ink-2">
            Google Sheets: last synced {relativeTime(sheet?.last_push || sheet?.last_pull)} · {sheet?.row_count || 0} rows ·{" "}
            {sheet?.status === "error" || sheet?.error ? "❌" : "✅"}
          </p>
          {sheet?.error ? <p className="mt-1 font-mono text-xs text-acc">{sheet.error}</p> : null}
        </div>
        <Button variant="secondary" loading={syncing} onClick={syncNow}>
          Sync now
        </Button>
      </Card>

      {best && worst && best !== worst ? (
        <p className="rounded-[2px] border border-l-4 border-deep bg-deep/10 px-4 py-3 text-sm text-ink">
          <span className="font-semibold">{best.source}</span> converts {ratio}x better than{" "}
          <span className="font-semibold">{worst.source}</span> — consider shifting spend.
        </p>
      ) : null}

      {loading && !rows ? (
        <LoadingCard label="Loading source stats…" />
      ) : error && !rows?.length ? (
        <ErrorState message={error} onRetry={load} />
      ) : rows?.length ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Total sign-ups" value={totals.signups} tone="sky" />
            <StatCard label="Total Fit" value={totals.fit} tone="emerald" />
            <StatCard label="Total Completed" value={totals.completed} tone="rose" />
          </div>
          <Card className="!p-0">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
              <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">01 / Funnel by source</h2>
              <div className="flex items-center gap-3 font-mono text-[11px] text-ink-2">
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 bg-ink" aria-hidden="true" /> Sign-ups
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 bg-deep" aria-hidden="true" /> Fit
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 bg-acc" aria-hidden="true" /> Completed
                </span>
              </div>
            </div>
            <div className="px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
              <Table>
                <thead>
                  <tr>
                    <Th>Source</Th>
                    <Th>Type</Th>
                    <Th>Sign-ups</Th>
                    <Th>Fit</Th>
                    <Th>Completed</Th>
                    <Th>Conversion</Th>
                    <Th>Completion rate</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.source} className="hover:bg-paper-2">
                      <Td className="font-medium">{r.source}</Td>
                      <Td className="font-mono text-xs text-ink-2">{r.type}</Td>
                      <Td>
                        <FunnelBar value={r.signups} max={max} color="var(--color-ink)" />
                      </Td>
                      <Td>
                        <FunnelBar value={r.fit} max={max} color="var(--color-deep)" />
                      </Td>
                      <Td>
                        <FunnelBar value={r.completed} max={max} color="var(--color-acc)" />
                      </Td>
                      <Td className="font-mono text-xs tabular-nums">
                        {r.signups ? Math.round((r.completed / r.signups) * 100) : 0}%
                      </Td>
                      <Td>
                        <QualityBar
                          rate={r.completion_rate || 0}
                          fill={
                            best && r.source === best.source
                              ? "var(--color-deep)"
                              : worst && r.source === worst.source
                                ? "var(--color-acc)"
                                : "var(--color-ink-3)"
                          }
                        />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </Card>
        </>
      ) : (
        <EmptyState title="No data yet" description="Source stats appear after the first signups." />
      )}
    </div>
  );
}
