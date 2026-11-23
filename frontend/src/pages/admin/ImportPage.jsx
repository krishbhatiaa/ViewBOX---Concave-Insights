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
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function pick(e) {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setReport(null);
    setError("");
  }

  async function run() {
    if (!file) {
      setError("Please choose a CSV file first.");
      return;
    }
    setLoading(true);
    setError("");
    setReport(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const d = await api("/api/admin/import", { method: "POST", body: fd, role: "admin" });
      setReport(d);
      toast(`Import finished: ${d.imported} imported, ${d.skipped} skipped`);
      if (fileRef.current) fileRef.current.value = "";
      setFile(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Import respondents"
        description="Upload a messy CSV — bad rows are fixed or skipped with a reason; the import never crashes."
      />

      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="csv-file" className="mb-1 block text-sm font-medium">
              CSV file
            </label>
            <Input
              ref={fileRef}
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={pick}
              className="!py-2.5 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100 dark:file:bg-indigo-950 dark:file:text-indigo-300"
            />
          </div>
          <Button onClick={run} loading={loading} disabled={!file}>
            {report ? "Import again" : "Import"}
          </Button>
        </div>
        {file && !loading && (
          <p className="mt-2 text-sm text-slate-500">
            Selected: <b>{file.name}</b> ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}
        {error && (
          <div className="mt-3">
            <InlineError message={error} />
          </div>
        )}
        <p className="mt-3 text-xs text-slate-500">
          Expected columns: name, phone, DOB, gender, city, income, interests, source (header names are matched
          case-insensitively). Try <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">data/messy_sample.csv</code>.
        </p>
      </Card>

      {loading && (
        <Card aria-busy="true">
          <p className="text-sm font-medium">Importing…</p>
          <div className="mt-3 space-y-2">
            <div className="h-8 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
            <div className="h-8 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
            <div className="h-8 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
          </div>
        </Card>
      )}

      {report && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total rows" value={report.total_rows} tone="slate" />
            <StatCard label="Imported" value={report.imported} tone="emerald" />
            <StatCard label="Fixed" value={report.fixed} tone="amber" />
            <StatCard label="Skipped" value={report.skipped} tone="rose" />
          </div>

          <Card className="!p-0">
            <div className="flex items-center justify-between px-4 pt-4 sm:px-5">
              <h2 className="text-base font-semibold">Per-row report</h2>
              {report.details.length === 0 && <span className="text-sm text-slate-500">No issues found</span>}
            </div>
            <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
              {report.details.length ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>Row</Th>
                      <Th>Action</Th>
                      <Th>Reason</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.details.map((d, i) => (
                      <tr key={i}>
                        <Td className="tabular-nums">{d.row}</Td>
                        <Td>
                          <Tag tone={d.action === "fixed" ? "amber" : "rose"}>{d.action}</Tag>
                        </Td>
                        <Td className="whitespace-normal text-slate-600 dark:text-slate-300">{d.reason}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState title="Every row imported cleanly" description="No fixes or skips were needed." />
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
