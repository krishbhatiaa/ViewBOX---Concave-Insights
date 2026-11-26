import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import Modal from "../../components/Modal.jsx";
import { useToast } from "../../components/Toast.jsx";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  InlineError,
  Input,
  LoadingCard,
  PageHeader,
  Select,
  StageTag,
  Table,
  Td,
  Textarea,
  Th,
} from "../../components/ui.jsx";

const STAGES = ["", "Lead", "Fit", "Completed", "Failed"];

export default function AdminReferralsPage() {
  const toast = useToast();
  const [stage, setStage] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [dialog, setDialog] = useState(null);
  const [surveys, setSurveys] = useState([]);
  const [surveyId, setSurveyId] = useState("");
  const [quality, setQuality] = useState(true);
  const [reason, setReason] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (stage) params.set("stage", stage);
    if (q.trim()) params.set("q", q.trim());
    try {
      setRows(await api(`/api/admin/referrals?${params}`, { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [stage, q]);

  useEffect(() => {
    load();
  }, [load]);

  function openDialog(row, kind) {
    setDialogError("");
    setReason("");
    setQuality(true);
    setSurveys([]);
    setSurveyId("");
    if (kind === "Completed") {
      api("/api/admin/surveys", { role: "admin" })
        .then((all) => {
          const usable = all.filter((s) => s.status === "live" || s.status === "closed");
          setSurveys(usable);
          setSurveyId(usable.length ? String(usable[0].id) : "");
          if (!usable.length) setDialogError("Create or close a survey before marking this referral completed.");
        })
        .catch((err) => setDialogError(err.message));
    }
    setDialog({ row, kind });
  }

  async function saveDialog() {
    if (!dialog) return;
    setDialogError("");
    const { row, kind } = dialog;
    if (kind === "Completed" && !surveyId) {
      setDialogError("Please choose which survey was completed.");
      return;
    }
    if (kind === "Failed" && !reason.trim()) {
      setDialogError("Please give a reason when marking Failed — it is shown to the referrer.");
      return;
    }
    const body = kind === "Completed"
      ? { stage: "Completed", survey_id: Number(surveyId), quality_check_passed: quality }
      : kind === "Failed"
        ? { stage: "Failed", failure_reason: reason.trim() }
        : { stage: "Fit" };
    setSaving(true);
    try {
      await api(`/api/admin/referrals/${row.id}/stage`, { method: "POST", body, role: "admin" });
      toast(`${row.member} moved to ${kind}`);
      setDialog(null);
      load();
    } catch (err) {
      setDialogError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader kicker="ADMIN / 02" title="Referrals" description="Move invited friends through Lead, Fit, Completed and Failed." />

      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Stage" id="ref-stage">
            <Select id="ref-stage" value={stage} onChange={(e) => setStage(e.target.value)}>
              {STAGES.map((value) => (
                <option key={value || "all"} value={value}>{value || "All stages"}</option>
              ))}
            </Select>
          </Field>
          <Field label="Search" id="ref-q">
            <Input id="ref-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, city or reason…" />
          </Field>
        </div>
      </Card>

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

      {loading && !rows ? (
        <LoadingCard label="Loading referrals…" />
      ) : error && !rows?.length ? (
        <ErrorState message={error} onRetry={load} />
      ) : rows?.length ? (
        <Card className="!p-0">
          <p className="border-b border-line px-4 py-3 font-mono text-xs text-ink-2 sm:px-5">
            {rows.length} referral{rows.length > 1 ? "s" : ""}
            {loading && " · updating…"}
          </p>
          <div className="px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th>
                  <Th>Referred friend</Th>
                  <Th>Referrer</Th>
                  <Th>Source</Th>
                  <Th>Stage</Th>
                  <Th>Note</Th>
                  <Th>Updated</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-paper-2">
                    <Td className="font-mono text-xs tabular-nums text-ink-2">{r.id}</Td>
                    <Td>
                      <span className="font-medium">{r.member || "(deleted)"}</span>
                      <span className="block font-mono text-xs text-ink-2">#{r.member_id} · {r.city || "—"}</span>
                    </Td>
                    <Td>
                      {r.referrer || "—"}
                      <span className="block font-mono text-xs text-ink-2">{r.referrer_id ? `#${r.referrer_id}` : "direct"}</span>
                    </Td>
                    <Td>{r.source || "—"}</Td>
                    <Td><StageTag stage={r.stage} /></Td>
                    <Td className="max-w-56 whitespace-normal text-xs text-ink-2">{r.failure_reason || "—"}</Td>
                    <Td className="font-mono text-xs tabular-nums text-ink-2">{r.updated_at ? r.updated_at.slice(0, 10) : "—"}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          variant="secondary"
                          className="min-h-11 !px-2.5 !text-xs"
                          disabled={r.stage !== "Lead"}
                          onClick={() => openDialog(r, "Fit")}
                        >
                          Mark Fit
                        </Button>
                        <Button
                          variant="secondary"
                          className="min-h-11 !px-2.5 !text-xs"
                          disabled={r.stage === "Completed"}
                          onClick={() => openDialog(r, "Completed")}
                        >
                          Completed
                        </Button>
                        <Button
                          variant="danger"
                          className="min-h-11 !px-2.5 !text-xs"
                          disabled={r.stage === "Completed" || r.stage === "Failed"}
                          onClick={() => openDialog(r, "Failed")}
                        >
                          Failed
                        </Button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="No referrals match these filters"
          description="Try another stage or search term — referrals appear here after signup."
        />
      )}

      <Modal
        open={!!dialog}
        onClose={() => setDialog(null)}
        title={dialog?.kind === "Completed" ? "Mark as completed" : dialog?.kind === "Failed" ? "Mark as failed" : "Mark as Fit"}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-2">
            {dialog?.kind === "Fit"
              ? `Confirm that ${dialog?.row?.member || "this friend"} is a good fit.`
              : dialog?.kind === "Completed"
                ? "Completed is irreversible. Pending payouts will be created for the friend and the referrer when the quality check passes."
                : "The referrer will see this reason in My referrals."}
          </p>

          {dialog?.kind === "Completed" && (
            <>
              <Field label="Which survey?" id="ref-survey" required>
                <Select id="ref-survey" value={surveyId} onChange={(e) => setSurveyId(e.target.value)}>
                  <option value="">Choose a survey</option>
                  {surveys.map((s) => (
                    <option key={s.id} value={s.id}>{s.title} ({s.status})</option>
                  ))}
                </Select>
              </Field>
              <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={quality}
                  onChange={(e) => setQuality(e.target.checked)}
                  className="h-5 w-5 rounded-[2px] border-line-2 accent-acc"
                />
                Quality check passed
                <span className="font-mono text-xs text-ink-2">(creates Pending payouts)</span>
              </label>
            </>
          )}

          {dialog?.kind === "Failed" && (
            <Field label="Reason" id="ref-reason" required hint="Shown to the referrer in plain words.">
              <Textarea
                id="ref-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Did not match profile criteria"
              />
            </Field>
          )}

          {dialogError && <InlineError message={dialogError} />}
          <div className="flex flex-wrap gap-2">
            <Button onClick={saveDialog} loading={saving} disabled={saving}>
              Confirm {dialog?.kind}
            </Button>
            <Button variant="secondary" onClick={() => setDialog(null)}>Cancel</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
