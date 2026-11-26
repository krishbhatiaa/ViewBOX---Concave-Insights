import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import Modal from "../../components/Modal.jsx";
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
  const [selected, setSelected] = useState([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);

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

  const selectable = rows ? rows.filter((p) => p.status !== "Paid") : [];
  const selectedRows = rows ? rows.filter((p) => selected.includes(p.id)) : [];
  const selectedTotal = selectedRows.reduce((sum, p) => sum + Number(p.amount || 0), 0);

  const toggle = (id) => setSelected((current) => current.includes(id)
    ? current.filter((x) => x !== id) : [...current, id]);

  const toggleAll = () => setSelected(selected.length === selectable.length ? [] : selectable.map((p) => p.id));

  const approveSelected = async () => {
    setBatchBusy(true);
    try {
      const result = await api("/api/admin/payouts/batch-approve",
                               { method: "POST", body: { ids: selected }, role: "admin" });
      toast(`Approved ${result.approved} payout(s), ${result.failed} failed`, result.failed ? "error" : "success");
      setSelected([]);
      setConfirmOpen(false);
      load();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBatchBusy(false);
    }
  };

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
        kicker="ADMIN / 09"
        title="Payout ledger"
        description="Survey payments and referral bonuses. Every payout carries a UTR reference; ops approves before it can be marked Paid."
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
              <Card key={s} className="border-t-2 border-t-ink !p-4">
                <p className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">{s} total</p>
                <p className="mt-1 font-display text-3xl font-normal tabular-nums text-ink">₹{money(totals[s] || 0)}</p>
              </Card>
            ))}
          </div>

          <Card className="!p-0">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
              <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">All payouts</h2>
              <Button variant="secondary" disabled={!selected.length} onClick={() => setConfirmOpen(true)}>
                Approve selected
              </Button>
            </div>
            <div className="px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
              <Table>
                <thead>
                  <tr>
                    <Th>
                      <input type="checkbox" aria-label="Select all payouts" className="h-5 w-5 rounded-[2px] border-line-2 accent-acc"
                             checked={!!selectable.length && selected.length === selectable.length}
                             onChange={toggleAll} disabled={!selectable.length} />
                    </Th>
                    <Th>ID</Th>
                    <Th>Member</Th>
                    <Th>Kind</Th>
                    <Th>Amount</Th>
                    <Th>UTR / transaction ID</Th>
                    <Th>Status</Th>
                    <Th>Action</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id} className="hover:bg-paper-2">
                      <Td>
                        <input type="checkbox" aria-label={`Select payout ${p.id}`} className="h-5 w-5 rounded-[2px] border-line-2 accent-acc"
                               checked={selected.includes(p.id)} onChange={() => toggle(p.id)}
                               disabled={p.status === "Paid"} />
                      </Td>
                      <Td className="font-mono text-xs tabular-nums text-ink-2">{p.id}</Td>
                      <Td className="font-medium">{p.member}</Td>
                      <Td>{p.kind}</Td>
                      <Td className="font-mono font-medium tabular-nums">₹{money(p.amount)}</Td>
                      <Td className="font-mono text-xs text-ink-2">{p.utr || "—"}</Td>
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
                          {p.status === "Paid" && <span className="font-mono text-xs text-ink-2">Settled</span>}
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

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Approve selected payouts">
        <p className="text-sm text-ink-2">
          Approve {selectedRows.length} payout(s) totalling ₹{money(selectedTotal)}?
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button loading={batchBusy} onClick={approveSelected}>Confirm</Button>
        </div>
      </Modal>
    </div>
  );
}
