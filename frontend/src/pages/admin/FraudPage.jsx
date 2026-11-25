import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  InlineError,
  PageHeader,
  Select,
  StatCard,
  Table,
  Tag,
  Td,
  Th,
} from "../../components/ui.jsx";

const STATUSES = [
  { value: "open", label: "Open" },
  { value: "Cleared", label: "Cleared" },
  { value: "Confirmed", label: "Confirmed" },
  { value: "all", label: "All" },
];

const TYPE_LABELS = {
  duplicate_signup: "Duplicate sign-up",
  self_referral: "Self-referral",
  burst_signups: "Burst sign-ups",
  referral_ring: "Referral ring",
};

const TYPE_TONES = {
  duplicate_signup: "rose",
  self_referral: "rose",
  burst_signups: "amber",
  referral_ring: "indigo",
};

export default function FraudPage() {
  const toast = useToast();
  const [status, setStatus] = useState("open");
  const [flags, setFlags] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [acting, setActing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setFlags(await api(`/api/admin/fraud-flags?status=${encodeURIComponent(status)}`, { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  async function review(flag, next) {
    setActing(flag.id);
    try {
      await api(`/api/admin/fraud-flags/${flag.id}/review`, { method: "POST", body: { status: next }, role: "admin" });
      toast(`${TYPE_LABELS[flag.flag_type] || flag.flag_type} for ${flag.name} → ${next}`);
      load();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setActing(null);
    }
  }

  async function runScan() {
    setScanning(true);
    try {
      const d = await api("/api/admin/fraud/scan", { method: "POST", role: "admin" });
      toast(d.flags_created ? `Scan finished: ${d.flags_created} new flag(s)` : "Scan finished: no new issues found");
      load();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setScanning(false);
    }
  }

  const openCount = flags?.filter((f) => f.status === "open").length ?? null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Fraud review queue"
        description="Duplicate sign-ups, self-referrals, device/IP bursts and referral rings. Flags are never deleted — review sets them to Cleared or Confirmed."
        actions={
          <Button variant="secondary" onClick={runScan} loading={scanning}>
            Run scan
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Showing" value={flags?.length ?? "…"} tone="slate" />
        <StatCard label="Open in view" value={openCount ?? "…"} tone="rose" />
        <StatCard label="Cleared" value={flags?.filter((f) => f.status === "Cleared").length ?? "…"} tone="emerald" />
        <StatCard label="Confirmed" value={flags?.filter((f) => f.status === "Confirmed").length ?? "…"} tone="amber" />
      </div>

      <Card>
        <div className="max-w-xs">
          <label htmlFor="flag-status" className="mb-1 block text-sm font-medium">
            Show
          </label>
          <Select id="flag-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {error && !flags ? (
        <ErrorState message={error} onRetry={load} />
      ) : loading && !flags ? (
        <Card aria-busy="true">
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
            ))}
          </div>
        </Card>
      ) : flags?.length ? (
        <Card className="!p-0">
          <p className="px-4 pt-4 text-sm text-slate-500 sm:px-5">{flags.length} flag(s)</p>
          <div className="mt-2 px-4 pb-4 sm:px-5 sm:pb-5">
            <Table>
              <thead>
                <tr>
                  <Th>Member</Th>
                  <Th>Phone</Th>
                  <Th>Type</Th>
                  <Th>Details</Th>
                  <Th>Raised</Th>
                  <Th>Status</Th>
                  <Th>Action</Th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td className="font-medium">{f.name}</Td>
                    <Td className="tabular-nums">{f.phone || "—"}</Td>
                    <Td>
                      <Tag tone={TYPE_TONES[f.flag_type] || "slate"}>{TYPE_LABELS[f.flag_type] || f.flag_type}</Tag>
                    </Td>
                    <Td className="max-w-sm whitespace-normal text-slate-600 dark:text-slate-300">{f.details}</Td>
                    <Td className="text-slate-500">{f.created_at}</Td>
                    <Td>
                      <Tag tone={f.status === "open" ? "rose" : f.status === "Cleared" ? "emerald" : "amber"}>
                        {f.status}
                      </Tag>
                    </Td>
                    <Td>
                      {f.status === "open" ? (
                        <div className="flex flex-wrap gap-1.5">
                          <Button
                            variant="secondary"
                            className="min-h-11 !px-2.5 !text-xs"
                            disabled={acting === f.id}
                            onClick={() => review(f, "Cleared")}
                          >
                            Clear
                          </Button>
                          <Button
                            variant="danger"
                            className="min-h-11 !px-2.5 !text-xs"
                            disabled={acting === f.id}
                            onClick={() => review(f, "Confirmed")}
                          >
                            Confirm
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          {f.reviewed_by ? `by ${f.reviewed_by}` : "reviewed"}
                        </span>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title={status === "open" ? "No open flags" : "No flags here"}
          description={
            status === "open"
              ? "Nothing to review. Run a scan to re-check existing members for bursts and rings."
              : "Try another status filter."
          }
        />
      )}

      {error && flags && <InlineError message={error} />}
    </div>
  );
}
