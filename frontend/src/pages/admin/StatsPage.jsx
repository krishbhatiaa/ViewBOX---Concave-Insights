import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  BAR_TONES,
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

export default function StatsPage() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    load();
  }, [load]);

  const max = rows ? Math.max(...rows.map((r) => r.signups), 1) : 1;
  const totals = rows
    ? rows.reduce((a, r) => ({ signups: a.signups + r.signups, fit: a.fit + r.fit, completed: a.completed + r.completed }), {
        signups: 0,
        fit: 0,
        completed: 0,
      })
    : null;

  return (
    <div className="space-y-5">
      <PageHeader title="Source dashboard" description="Sign-ups, Fit and Completed per channel — sorted by volume." />

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

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
