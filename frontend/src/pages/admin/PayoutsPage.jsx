import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingCard,
  PageHeader,
  StageTag,
  Table,
  Td,
  Th,
} from "../../components/ui.jsx";

export default function PayoutsPage() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api("/api/admin/payouts", { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(id, status) {
    setBusyId(id);
    try {
      await api(`/api/admin/payouts/${id}/status`, { method: "POST", body: { status }, role: "admin" });
      toast(`Payout ${id} marked as ${status}`);
      load();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusyId(null);
    }
  }

  const totals = rows
    ? rows.reduce(
        (a, p) => {
          a[p.status] = (a[p.status] || 0) + p.amount;
          return a;
        },
        {}
      )
    : {};

  return (
    <div className="space-y-5">
      <PageHeader
        title="Payout ledger"
        description="Survey payments and referral bonuses. Ops approves each row before it can be marked Paid."
      />

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

      {loading && !rows ? (
        <LoadingCard label="Loading payouts…" />
      ) : error && !rows?.length ? (
        <ErrorState message={error} onRetry={load} />
      ) : rows?.length ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {["Pending", "Approved", "Paid"].map((s) => (
              <Card key={s} className="!p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{s} total</p>
                <p className="mt-1 text-2xl font-bold">₹{money(totals[s] || 0)}</p>
              </Card>
            ))}
          </div>

          <Card className="!p-0">
            <div className="px-4 pt-4 sm:px-5">
              <h2 className="text-base font-semibold">All payouts</h2>
            </div>
            <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
              <Table>
                <thead>
                  <tr>
                    <Th>ID</Th>
                    <Th>Member</Th>
                    <Th>Kind</Th>
                    <Th>Amount</Th>
                    <Th>Status</Th>
                    <Th>Action</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id}>
                      <Td className="tabular-nums text-slate-500">{p.id}</Td>
                      <Td className="font-medium">{p.member}</Td>
                      <Td>{p.kind}</Td>
                      <Td className="font-medium tabular-nums">₹{money(p.amount)}</Td>
                      <Td>
                        <StageTag stage={p.status} />
                      </Td>
                      <Td>
                        <div className="flex gap-1.5">
                          {p.status === "Pending" && (
                            <Button
                              variant="secondary"
                              className="min-h-11 !px-2.5 !text-xs"
                              loading={busyId === p.id}
                              onClick={() => setStatus(p.id, "Approved")}
                            >
                              Approve
                            </Button>
                          )}
                          {p.status === "Approved" && (
                            <Button
                              className="min-h-11 !px-2.5 !text-xs"
                              loading={busyId === p.id}
                              onClick={() => setStatus(p.id, "Paid")}
                            >
                              Mark paid
                            </Button>
                          )}
                          {p.status === "Paid" && <span className="text-xs text-slate-500 dark:text-slate-400">Settled</span>}
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </Card>
        </>
      ) : (
        <EmptyState
          title="No payouts yet"
          description="Payout rows are created automatically when a member completes a survey or a referral bonus is earned."
        />
      )}
    </div>
  );
}
