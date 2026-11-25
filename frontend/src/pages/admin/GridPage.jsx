import { useCallback, useEffect, useState } from "react";
import { api, downloadBlob } from "../../api.js";
import { useDebounced } from "../../hooks/useDebounced.js";
import { useToast } from "../../components/Toast.jsx";
import Modal from "../../components/Modal.jsx";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  InlineError,
  Input,
  PageHeader,
  Select,
  StageTag,
  Table,
  Td,
  Textarea,
  Th,
} from "../../components/ui.jsx";

const STAGE_STATUSES = [
  { value: "", label: "All statuses" },
  { value: "Lead", label: "Lead" },
  { value: "Fit", label: "Fit" },
  { value: "Completed", label: "Completed" },
  { value: "Failed", label: "Failed" },
  { value: "flagged", label: "Flagged" },
];
// per-survey results: only selectable once a survey is chosen
const ELIGIBILITY_STATUSES = ["Approved", "Rejected", "Waitlisted"];
const isEligibilityStatus = (s) => ELIGIBILITY_STATUSES.includes(s);

export default function GridPage() {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [city, setCity] = useState("");
  const [status, setStatus] = useState("");
  const [filterSurveyId, setFilterSurveyId] = useState("");
  const [filterSurveys, setFilterSurveys] = useState([]);
  const [sources, setSources] = useState([]);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const dq = useDebounced(q, 300);
  const dCity = useDebounced(city, 300);

  const qs = useCallback(() => {
    const p = new URLSearchParams();
    if (dq) p.set("q", dq);
    if (sourceId) p.set("source_id", sourceId);
    if (dCity) p.set("city", dCity);
    if (status) p.set("status", status);
    if (filterSurveyId) p.set("survey_id", filterSurveyId);
    return p.toString();
  }, [dq, sourceId, dCity, status, filterSurveyId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const d = await api(`/api/admin/members?${qs()}`, { role: "admin" });
      setRows(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [qs]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api("/api/admin/sources", { role: "admin" })
      .then(setSources)
      .catch(() => {});
    api("/api/admin/surveys", { role: "admin" })
      .then(setFilterSurveys)
      .catch(() => {});
  }, []);

  async function exportView(fmt) {
    setExporting(true);
    try {
      const blob = await api(`/api/admin/members/export?${qs()}&format=${fmt}`, { role: "admin", raw: true });
      downloadBlob(blob, fmt === "xlsx" ? "members.xlsx" : "members.csv");
      toast(`Exported the current view as members.${fmt}`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setExporting(false);
    }
  }

  // stage-change modal state
  const [dialog, setDialog] = useState(null); // {row, kind:'Completed'|'Failed'}
  const [surveys, setSurveys] = useState([]);
  const [surveyId, setSurveyId] = useState("");
  const [quality, setQuality] = useState(true);
  const [reason, setReason] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [saving, setSaving] = useState(false);

  async function markFit(row) {
    try {
      await api(`/api/admin/referrals/${row.referral_id}/stage`, {
        method: "POST",
        body: { stage: "Fit" },
        role: "admin",
      });
      toast(`${row.name} marked as Fit`);
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function openDialog(row, kind) {
    setDialogError("");
    setReason("");
    setQuality(true);
    if (kind === "Completed") {
      try {
        const sv = await api("/api/admin/surveys", { role: "admin" });
        if (!sv.length) {
          toast("Create a survey first (Surveys tab).", "error");
          return;
        }
        setSurveys(sv);
        setSurveyId(String(sv[0].id));
      } catch (err) {
        toast(err.message, "error");
        return;
      }
    }
    setDialog({ row, kind });
  }

  async function saveDialog() {
    const { row, kind } = dialog;
    setDialogError("");
    if (kind === "Failed" && !reason.trim()) {
      setDialogError("Please give a reason when marking Failed — it is shown to the referrer.");
      return;
    }
    if (kind === "Completed" && !surveyId) {
      setDialogError("Please choose which survey was completed.");
      return;
    }
    setSaving(true);
    try {
      const body =
        kind === "Completed"
          ? { stage: "Completed", survey_id: Number(surveyId), quality_check_passed: quality }
          : { stage: "Failed", failure_reason: reason.trim() };
      await api(`/api/admin/referrals/${row.referral_id}/stage`, { method: "POST", body, role: "admin" });
      setDialog(null);
      toast(`${row.name} → ${kind === "Completed" && !quality ? "Failed (quality check)" : kind}`);
      load();
    } catch (err) {
      setDialogError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const filtersActive = dq || sourceId || dCity || status || filterSurveyId;

  function clearFilters() {
    setQ("");
    setSourceId("");
    setCity("");
    setStatus("");
    setFilterSurveyId("");
  }

  // manual eligibility override state
  const [ovDialog, setOvDialog] = useState(null); // {row}
  const [ovExisting, setOvExisting] = useState(null);
  const [ovSurveyId, setOvSurveyId] = useState("");
  const [ovReason, setOvReason] = useState("");
  const [ovError, setOvError] = useState("");
  const [ovSaving, setOvSaving] = useState(false);

  async function openOverride(row) {
    setOvError("");
    setOvReason("");
    try {
      const [sv, ovs] = await Promise.all([
        api("/api/admin/surveys", { role: "admin" }),
        api(`/api/admin/overrides?member_id=${row.id}`, { role: "admin" }),
      ]);
      if (!sv.length && !ovs.length) {
        toast("Create a survey first (Surveys tab).", "error");
        return;
      }
      setSurveys(sv);
      setOvSurveyId(sv.length ? String(sv[0].id) : "");
      setOvExisting(ovs[0] || null);
      setOvDialog({ row });
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function saveOverride() {
    setOvError("");
    if (!ovSurveyId) {
      setOvError("Please choose which survey to override.");
      return;
    }
    if (ovReason.trim().length < 3) {
      setOvError("Please give a short reason — it is stored with the override.");
      return;
    }
    setOvSaving(true);
    try {
      await api("/api/admin/overrides", {
        method: "POST",
        body: { member_id: ovDialog.row.id, survey_id: Number(ovSurveyId), reason: ovReason.trim() },
        role: "admin",
      });
      toast(`${ovDialog.row.name} will be Approved for that survey`);
      setOvDialog(null);
      load();
    } catch (err) {
      setOvError(err.message);
    } finally {
      setOvSaving(false);
    }
  }

  async function removeOverride() {
    setOvError("");
    setOvSaving(true);
    try {
      await api(`/api/admin/overrides/${ovExisting.id}`, { method: "DELETE", role: "admin" });
      toast("Override removed — normal rules apply again");
      setOvDialog(null);
      load();
    } catch (err) {
      setOvError(err.message);
    } finally {
      setOvSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Members"
        description="Search, filter, change referral stages, and export exactly what you see."
        actions={
          <>
            <Button variant="secondary" onClick={() => exportView("csv")} loading={exporting} disabled={!rows?.length}>
              Export CSV
            </Button>
            <Button variant="secondary" onClick={() => exportView("xlsx")} loading={exporting} disabled={!rows?.length}>
              Export Excel
            </Button>
          </>
        }
      />

      {/* sticky filter bar */}
      <div className="sticky top-[57px] z-20 -mx-4 mb-4 border-b border-slate-200 bg-slate-50/95 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 sm:mx-0 sm:rounded-xl sm:border sm:px-4">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          <Field label="Search" id="grid-q">
            <Input
              id="grid-q"
              placeholder="Name, ID or city…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              type="search"
            />
          </Field>
          <Field label="Source" id="grid-src">
            <Select id="grid-src" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="City" id="grid-city">
            <Input id="grid-city" placeholder="Any city…" value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          <Field label="Survey result" id="grid-survey" hint={filterSurveyId ? undefined : "Pick a survey to see Approved / Rejected / Waitlisted."}>
            <Select
              id="grid-survey"
              value={filterSurveyId}
              onChange={(e) => {
                setFilterSurveyId(e.target.value);
                if (!e.target.value && isEligibilityStatus(status)) setStatus(""); // result needs a survey
              }}
            >
              <option value="">No survey selected</option>
              {filterSurveys.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Status" id="grid-status">
            <Select id="grid-status" value={status} onChange={(e) => setStatus(e.target.value)}>
              <optgroup label="Pipeline">
                {STAGE_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Survey result (needs a survey)">
                {ELIGIBILITY_STATUSES.map((s) => (
                  <option key={s} value={s} disabled={!filterSurveyId}>
                    {s}
                  </option>
                ))}
              </optgroup>
            </Select>
          </Field>
        </div>
        {filtersActive && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500">Filters active</span>
            <Button variant="ghost" className="!min-h-8 !px-2 !text-xs" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        )}
      </div>

      {error && !rows ? (
        <ErrorState message={error} onRetry={load} />
      ) : loading && !rows ? (
        <Card aria-busy="true">
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
            ))}
          </div>
        </Card>
      ) : rows?.length ? (
        <Card className="!p-0">
          <p className="px-4 pt-4 text-sm text-slate-500 sm:px-5">
            {rows.length} member{rows.length > 1 ? "s" : ""}
            {loading && " · updating…"}
          </p>
          <div className="mt-2 px-4 pb-4 sm:px-5 sm:pb-5">
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th>
                  <Th>Name</Th>
                  <Th>Phone</Th>
                  <Th>City</Th>
                  <Th>Source</Th>
                  <Th>Referrer</Th>
                  <Th>Stage</Th>
                  {filterSurveyId && <Th>Survey result</Th>}
                  <Th>Joined</Th>
                  <Th>Action</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <Td className="tabular-nums text-slate-500">{m.id}</Td>
                    <Td className="font-medium">{m.name}</Td>
                    <Td className="tabular-nums">{m.phone}</Td>
                    <Td>{m.city || "—"}</Td>
                    <Td>{m.source}</Td>
                    <Td>{m.referrer || "—"}</Td>
                    <Td>
                      <StageTag stage={m.stage} />
                    </Td>
                    {filterSurveyId && (
                      <Td>
                        {m.eligibility ? (
                          <span title={m.eligibility.reason} className="inline-flex flex-col gap-0.5">
                            <StageTag stage={m.eligibility.result} />
                            <span className="max-w-56 truncate text-xs text-slate-500">{m.eligibility.reason}</span>
                          </span>
                        ) : (
                          "—"
                        )}
                      </Td>
                    )}
                    <Td className="text-slate-500">{m.created_at}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1.5">
                        {m.referral_id && m.stage !== "Completed" && (
                          <>
                            {m.stage !== "Fit" && (
                              <Button variant="secondary" className="!min-h-9 !px-2.5 !text-xs" onClick={() => markFit(m)}>
                                Fit
                              </Button>
                            )}
                            <Button variant="secondary" className="!min-h-9 !px-2.5 !text-xs" onClick={() => openDialog(m, "Completed")}>
                              Completed
                            </Button>
                            {m.stage !== "Failed" && (
                              <Button variant="secondary" className="!min-h-9 !px-2.5 !text-xs" onClick={() => openDialog(m, "Failed")}>
                                Fail
                              </Button>
                            )}
                          </>
                        )}
                        <Button variant="ghost" className="!min-h-9 !px-2 !text-xs" onClick={() => openOverride(m)}>
                          Override…
                        </Button>
                        {!m.referral_id && <span className="text-xs text-slate-400">No referral row</span>}
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
          title={filtersActive ? "No members match these filters" : "No members yet"}
          description={filtersActive ? "Try clearing the filters or searching for something else." : "Members appear here after signups or CSV imports."}
          action={
            filtersActive ? (
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : null
          }
        />
      )}

      <Modal
        open={!!dialog}
        onClose={() => setDialog(null)}
        title={dialog?.kind === "Completed" ? "Mark as completed" : "Mark as failed"}
      >
        {dialog?.kind === "Completed" ? (
          <div className="space-y-4">
            <Field label="Which survey?" id="dlg-survey" required>
              <Select id="dlg-survey" value={surveyId} onChange={(e) => setSurveyId(e.target.value)}>
                {surveys.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} {s.completions >= (s.quota || Infinity) ? "(full)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={quality}
                onChange={(e) => setQuality(e.target.checked)}
                className="h-5 w-5 rounded border-slate-300 accent-indigo-600"
              />
              Quality check passed
              <span className="text-xs text-slate-500">(payment + cool-off only start when passed)</span>
            </label>
          </div>
        ) : (
          <Field label="Reason" id="dlg-reason" required hint="Shown to the referrer.">
            <Textarea
              id="dlg-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Did not match profile criteria"
            />
          </Field>
        )}
        {dialogError && (
          <div className="mt-3">
            <InlineError message={dialogError} />
          </div>
        )}
        <div className="mt-5 flex gap-2">
          <Button onClick={saveDialog} loading={saving} className="flex-1">
            Save
          </Button>
          <Button variant="secondary" onClick={() => setDialog(null)}>
            Cancel
          </Button>
        </div>
      </Modal>

      <Modal
        open={!!ovDialog}
        onClose={() => setOvDialog(null)}
        title={`Manual override — ${ovDialog?.row?.name || ""}`}
      >
        {ovExisting ? (
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              An override already exists for <b>{ovExisting.survey}</b>:
            </p>
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800">{ovExisting.reason}</p>
            <p className="text-xs text-slate-500">
              The member sees “Approved by the ops team after manual review” instead of the normal rules.
            </p>
            {ovError && <InlineError message={ovError} />}
            <div className="flex gap-2">
              <Button variant="danger" onClick={removeOverride} loading={ovSaving} className="flex-1">
                Remove override
              </Button>
              <Button variant="secondary" onClick={() => setOvDialog(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Approve this member for a survey regardless of the rules. The normal engine is skipped and the member
              sees that ops approved them after manual review.
            </p>
            <Field label="Which survey?" id="ov-survey" required>
              <Select id="ov-survey" value={ovSurveyId} onChange={(e) => setOvSurveyId(e.target.value)}>
                {surveys.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Reason" id="ov-reason" required hint="Stored with the override for audit.">
              <Textarea
                id="ov-reason"
                value={ovReason}
                onChange={(e) => setOvReason(e.target.value)}
                placeholder="e.g. Over quota but agreed with client"
              />
            </Field>
            {ovError && <InlineError message={ovError} />}
            <div className="flex gap-2">
              <Button onClick={saveOverride} loading={ovSaving} className="flex-1">
                Create override
              </Button>
              <Button variant="secondary" onClick={() => setOvDialog(null)}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
