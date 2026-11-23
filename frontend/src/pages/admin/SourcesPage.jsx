import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import { useToast } from "../../components/Toast.jsx";
import {
  Button,
  Card,
  CopyButton,
  EmptyState,
  ErrorState,
  Field,
  InlineError,
  Input,
  LoadingCard,
  PageHeader,
  Table,
  Td,
  Th,
} from "../../components/ui.jsx";

const TYPE_SUGGESTIONS = ["whatsapp", "staff", "instagram", "facebook", "website", "referral", "linkedin", "meta_ads"];

export default function SourcesPage() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [type, setType] = useState("");
  const [fieldError, setFieldError] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api("/api/admin/sources", { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(e) {
    e.preventDefault();
    const errs = {};
    if (name.trim().length < 2) errs.name = "Name needs at least 2 characters.";
    if (type.trim().length < 2) errs.type = "Type needs at least 2 characters (e.g. whatsapp).";
    setFieldError(errs);
    setFormError("");
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      await api("/api/admin/sources", { method: "POST", body: { name: name.trim(), type: type.trim() }, role: "admin" });
      toast(`Source "${name.trim()}" added — signed link ready below`);
      setName("");
      setType("");
      load();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Sources" description="Every signup channel gets a signed ?src= link. Forged links are ignored." />

      <Card>
        <h2 className="mb-3 text-base font-semibold">Add source</h2>
        <form onSubmit={submit} noValidate>
          {formError && (
            <div className="mb-3">
              <InlineError message={formError} />
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
            <Field label="Name" error={fieldError.name} required id="src-name">
              <Input
                id="src-name"
                value={name}
                error={fieldError.name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. WhatsApp - Pune"
              />
            </Field>
            <Field label="Type" error={fieldError.type} required id="src-type">
              <Input
                id="src-type"
                list="src-types"
                value={type}
                error={fieldError.type}
                onChange={(e) => setType(e.target.value)}
                placeholder="e.g. whatsapp"
              />
              <datalist id="src-types">
                {TYPE_SUGGESTIONS.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </Field>
            <Button type="submit" loading={saving}>
              Add source
            </Button>
          </div>
        </form>
      </Card>

      {loading && !rows ? (
        <LoadingCard label="Loading sources…" />
      ) : error && !rows ? (
        <ErrorState message={error} onRetry={load} />
      ) : rows?.length ? (
        <Card className="!p-0">
          <h2 className="px-4 pt-4 text-base font-semibold sm:px-5">All sources</h2>
          <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Type</Th>
                  <Th>Signed signup link</Th>
                  <Th>
                    <span className="sr-only">Copy</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <Td className="font-medium">{s.name}</Td>
                    <Td className="text-slate-500">{s.type}</Td>
                    <Td>
                      <input
                        readOnly
                        value={s.link}
                        aria-label={`Signed link for ${s.name}`}
                        onFocus={(e) => e.target.select()}
                        className="min-h-11 w-full min-w-56 rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
                      />
                    </Td>
                    <Td>
                      <CopyButton
                        value={s.link}
                        label="Copy"
                        className="!min-h-9 !px-2.5 !text-xs"
                        onCopied={() => toast("Link copied to clipboard")}
                      />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      ) : (
        <EmptyState title="No sources yet" description="Add the first channel above to start tracking signups." />
      )}
    </div>
  );
}
