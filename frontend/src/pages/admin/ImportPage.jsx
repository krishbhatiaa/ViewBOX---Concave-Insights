import { useRef, useState } from "react";
import { api } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import {
  Button,
  Card,
  EmptyState,
  InlineError,
  Input,
  PageHeader,
  StatCard,
  Table,
  Tag,
  Td,
  Th,
} from "../../components/ui.jsx";

export default function ImportPage() {
  const toast = useToast();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function pick(e) {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setPreview(null);
    setReport(null);
    setError("");
  }

  function reset() {
    if (fileRef.current) fileRef.current.value = "";
    setFile(null);
    setPreview(null);
    setReport(null);
    setError("");
  }

  async function run(dryRun) {
    if (!file) {
      setError("Please choose a CSV file first.");
      return;
    }
    setLoading(true);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const url = dryRun ? "/api/admin/import?dry_run=true" : "/api/admin/import";
      const d = await api(url, { method: "POST", body: fd, role: "admin" });
      if (dryRun) {
        setPreview(d);
        toast(
          `Preview ready: ${d.imported} would import, ${d.warned ?? 0} would need a look, ${d.skipped} would be skipped`,
        );
      } else {
        setPreview(null);
        setReport(d);
        toast(
          `Import finished: ${d.imported} imported, ${d.warned ?? 0} need a look, ${d.skipped} skipped`,
        );
        if (fileRef.current) fileRef.current.value = "";
        setFile(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        kicker="ADMIN / 06"
        title="Import respondents"
        description="Preview a messy CSV first — nothing is saved until you confirm. Bad rows are fixed or skipped with a reason; the import never crashes."
      />

      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="csv-file" className="mb-1 block font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">
              CSV file
            </label>
            <Input
              ref={fileRef}
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={pick}
              className="!py-2 file:mr-3 file:rounded-[2px] file:border file:border-line-2 file:bg-paper-2 file:px-3 file:py-1.5 file:font-mono file:text-xs file:font-semibold file:uppercase file:tracking-wide file:text-ink hover:file:bg-paper-3"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => run(true)} loading={loading} disabled={!file}>
              {preview ? "Re-preview" : "Preview import"}
            </Button>
            <Button onClick={() => run(false)} loading={loading} disabled={!file || !preview}>
              Confirm import
            </Button>
          </div>
        </div>
        {file && !loading && (
          <p className="mt-2 font-mono text-xs text-ink-2">
            Selected: <b>{file.name}</b> ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}
        {preview && (
          <p className="mt-2 rounded-[2px] border border-l-4 border-line-2 border-l-acc bg-paper-3 px-3 py-2 text-sm text-ink">
            Preview only — nothing has been saved yet. Check the report below, then press{" "}
            <b>Confirm import</b>.
          </p>
        )}
        {error && (
          <div className="mt-3">
            <InlineError message={error} />
          </div>
        )}
        <p className="mt-3 text-xs text-ink-2">
          Expected columns: name, phone, DOB (or date_of_birth), gender, city, income, interests, source — plus
          member_id, referred_by, joined_on and last_survey_completed_on when you have them (header names are
          matched case-insensitively). Try{" "}
          <code className="rounded-[2px] border border-line bg-paper px-1 font-mono">data/viewbox_respondents_sample.csv</code>{" "}
          (the real 189-row sample) or{" "}
          <code className="rounded-[2px] border border-line bg-paper px-1 font-mono">data/messy_sample.csv</code>.
        </p>
      </Card>

      {loading && (
        <Card aria-busy="true">
          <p className="font-mono text-xs uppercase tracking-[.08em] text-ink-2">Importing…</p>
          <div className="mt-3 space-y-2">
            <div className="h-8 animate-pulse rounded-[2px] bg-paper-3" />
            <div className="h-8 animate-pulse rounded-[2px] bg-paper-3" />
            <div className="h-8 animate-pulse rounded-[2px] bg-paper-3" />
          </div>
        </Card>
      )}

      {(preview || report) && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total rows" value={(preview || report).total_rows} tone="slate" />
            <StatCard label={preview ? "Would import" : "Imported"} value={(preview || report).imported} tone="emerald" />
            <StatCard label={preview ? "Would fix" : "Fixed"} value={(preview || report).fixed} tone="amber" />
            <StatCard label={preview ? "Would warn" : "Warned"} value={(preview || report).warned ?? 0} tone="sky" />
            <StatCard label={preview ? "Would skip" : "Skipped"} value={(preview || report).skipped} tone="rose" />
          </div>

          <Card className="!p-0">
            <div className="flex items-center justify-between border-b border-line px-4 py-3 sm:px-5">
              <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">{preview ? "Per-row report (preview)" : "Per-row report"}</h2>
              {(preview || report).details.length === 0 && <span className="font-mono text-xs text-ink-2">No issues found</span>}
            </div>
            <div className="px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
              {(preview || report).details.length ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>Row</Th>
                      <Th>Action</Th>
                      <Th>Reason</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {(preview || report).details.map((d, i) => (
                      <tr key={i} className="hover:bg-paper-2">
                        <Td className="font-mono text-xs tabular-nums">{d.row}</Td>
                        <Td>
                          <Tag tone={d.action === "fixed" ? "amber" : d.action === "warned" ? "sky" : "rose"}>
                            {d.action}
                          </Tag>
                        </Td>
                        <Td className="whitespace-normal text-ink-2">{d.reason}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState
                  title={preview ? "Every row would import cleanly" : "Every row imported cleanly"}
                  description="No fixes, warnings or skips were needed."
                />
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
