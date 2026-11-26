import { useCallback, useEffect, useState } from "react";
import { api, sheetsPush, sheetsStatus } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  BAR_TONES,
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

function FunnelBar({ value, max, color }) {
  const pct = max > 0 ? Math.max((value / max) * 100, value > 0 ? 4 : 0) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2.5 w-28 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-sm font-medium">{value}</span>
    </div>
  );
}

function QualityBar({ rate, tone }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2.5 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${rate * 100}%` }} />
      </div>
      <span className="tabular-nums text-sm font-medium">{Math.round(rate * 100)}%</span>
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
      <PageHeader title="Source dashboard" description="Sign-ups, Fit and Completed per channel — sorted by volume." />

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

      <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Google Sheets</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Google Sheets: last synced {relativeTime(sheet?.last_push || sheet?.last_pull)} · {sheet?.row_count || 0} rows ·{" "}
            {sheet?.status === "error" || sheet?.error ? "❌" : "✅"}
          </p>
          {sheet?.error ? <p className="mt-1 text-sm text-rose-600 dark:text-rose-400">{sheet.error}</p> : null}
        </div>
        <Button variant="secondary" loading={syncing} onClick={syncNow}>
          Sync now
        </Button>
      </Card>

      {best && worst && best !== worst ? (
        <p className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900 dark:border-indigo-900 dark:bg-indigo-950 dark:text-indigo-100">
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
            <StatCard label="Total Fit" value={totals.fit} tone="amber" />
            <StatCard label="Total Completed" value={totals.completed} tone="emerald" />
          </div>
          <Card className="!p-0">
            <div className="px-4 pt-4 sm:px-5">
              <h2 className="text-base font-semibold">Funnel by source</h2>
            </div>
            <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
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
                    <tr key={r.source}>
                      <Td className="font-medium">{r.source}</Td>
                      <Td className="text-slate-500 dark:text-slate-400">{r.type}</Td>
                      <Td>
                        <FunnelBar value={r.signups} max={max} color={BAR_TONES.sky} />
                      </Td>
                      <Td>
                        <FunnelBar value={r.fit} max={max} color={BAR_TONES.amber} />
                      </Td>
                      <Td>
                        <FunnelBar value={r.completed} max={max} color={BAR_TONES.emerald} />
                      </Td>
                      <Td className="tabular-nums">
                        {r.signups ? Math.round((r.completed / r.signups) * 100) : 0}%
                      </Td>
                      <Td>
                        <QualityBar
                          rate={r.completion_rate || 0}
                          tone={best && r.source === best.source ? "bg-emerald-500"
                            : worst && r.source === worst.source ? "bg-rose-500" : BAR_TONES.sky}
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
