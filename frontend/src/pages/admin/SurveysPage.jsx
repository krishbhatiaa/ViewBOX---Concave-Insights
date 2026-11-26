import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../api.js";
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
  Table,
  Tag,
  Td,
  Th,
} from "../../components/ui.jsx";

const RULE_TYPES = [
  { value: "age", label: "Age", placeholder: "18-35" },
  { value: "city", label: "City", placeholder: "Mumbai,Pune,Delhi" },
  { value: "gender", label: "Gender", placeholder: "Male,Female" },
  { value: "income", label: "Income", placeholder: "5-10L,10L+" },
];

const CYCLE_DAYS = 15;
let ruleKey = 0;

function deadlineMax() {
  return new Date(Date.now() + CYCLE_DAYS * 86400000).toISOString().slice(0, 10);
}

function parseInterests(value) {
  const seen = new Set();
  return value.split(",").map((tag) => tag.trim().toLowerCase()).filter((tag) => {
    if (!tag || seen.has(tag)) return false;
    seen.add(tag);
    return true;
  });
}

function interestError(tags) {
  if (tags.length > 10) return "Use at most 10 interest tags.";
  if (tags.some((tag) => tag.length > 40)) return "Each interest tag must be 40 characters or fewer.";
  return "";
}

function RuleRow({ rule, onChange, onRemove }) {
  const meta = RULE_TYPES.find((t) => t.value === rule.rule_type) || RULE_TYPES[0];
  return (
    <div className="grid gap-2 rounded-lg border border-slate-200 p-3 dark:border-slate-700 sm:grid-cols-[1fr_2fr_1fr_auto]">
      <Select aria-label="Rule type" value={rule.rule_type} onChange={(e) => onChange({ ...rule, rule_type: e.target.value })}>
        {RULE_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </Select>
      <Input
        aria-label="Rule value"
        placeholder={meta.placeholder}
        value={rule.value}
        onChange={(e) => onChange({ ...rule, value: e.target.value })}
      />
      <Select
        aria-label="Strict or flexible"
        value={rule.strict_or_flexible}
        onChange={(e) => onChange({ ...rule, strict_or_flexible: e.target.value })}
      >
        <option value="strict">Strict</option>
        <option value="flexible">Flexible</option>
      </Select>
      <Button variant="secondary" className="!min-h-11" onClick={onRemove}>
        Remove
      </Button>
    </div>
  );
}

export default function SurveysPage() {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [form, setForm] = useState({ title: "", description: "", deadline: "", quota: "", amount: "0", interests: "" });
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ status: "live", deadline: "", quota: "", amount: "0", interests: "" });
  const [editError, setEditError] = useState("");
  const [editFieldErrors, setEditFieldErrors] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [rules, setRules] = useState([{ key: ++ruleKey, rule_type: "age", value: "", strict_or_flexible: "strict" }]);
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestNote, setSuggestNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await api("/api/admin/surveys", { role: "admin" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setEdit = (k) => (e) => setEditForm((f) => ({ ...f, [k]: e.target.value }));

  function openEdit(survey) {
    setEditError("");
    setEditFieldErrors({});
    setEditing(survey.id);
    setEditForm({
      status: survey.status,
      deadline: survey.deadline || "",
      quota: survey.quota ?? "",
      amount: survey.amount ?? 0,
      interests: (survey.interests || []).join(", "),
    });
  }

  async function saveEdit(e) {
    e.preventDefault();
    setEditError("");
    const tags = parseInterests(editForm.interests);
    const errs = {};
    const tagsError = interestError(tags);
    if (tagsError) errs.interests = tagsError;
    if (editForm.quota && Number(editForm.quota) < 1) errs.quota = "Quota must be at least 1, or left blank.";
    if (Number(editForm.amount) < 0) errs.amount = "Amount cannot be negative.";
    setEditFieldErrors(errs);
    if (Object.keys(errs).length) return;

    setSavingEdit(true);
    try {
      await api(`/api/admin/surveys/${editing}`, {
        method: "PATCH",
        body: {
          status: editForm.status,
          deadline: editForm.deadline ? `${editForm.deadline}T23:59:59` : null,
          quota: editForm.quota ? Number(editForm.quota) : null,
          amount: Number(editForm.amount) || 0,
          interests: tags,
        },
        role: "admin",
      });
      toast("Survey updated");
      setEditing(null);
      load();
    } catch (err) {
      setEditError(err.message);
      setEditFieldErrors((fe) => ({
        ...fe,
        deadline: err.message.toLowerCase().includes("deadline") ? err.message : fe.deadline,
      }));
    } finally {
      setSavingEdit(false);
    }
  }

  async function suggest() {
    setFormError("");
    setSuggestNote("");
    if (form.title.trim().length < 3) {
      setFieldErrors((fe) => ({ ...fe, title: "Write a title first — suggestions come from the title and description." }));
      return;
    }
    setSuggesting(true);
    try {
      const r = await api("/api/admin/suggest-rules", {
        method: "POST",
        body: { title: form.title.trim(), description: form.description.trim() },
        role: "admin",
      });
      setSuggestNote(r.note);
      if (r.rules.length) {
        setRules(r.rules.map((x) => ({ ...x, key: ++ruleKey })));
        toast(`Added ${r.rules.length} suggested rule${r.rules.length > 1 ? "s" : ""} — review before saving`);
      } else {
        toast("No rules could be suggested — add them manually", "error");
      }
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSuggesting(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setFormError("");
    const errs = {};
    if (form.title.trim().length < 3) errs.title = "Title needs at least 3 characters.";
    if (form.quota && Number(form.quota) < 1) errs.quota = "Quota must be at least 1, or left blank.";
    if (Number(form.amount) < 0) errs.amount = "Amount cannot be negative.";
    const interests = parseInterests(form.interests);
    const interestsProblem = interestError(interests);
    if (interestsProblem) errs.interests = interestsProblem;
    const filled = rules.filter((r) => r.value.trim());
    const emptyRule = rules.some((r) => !r.value.trim() && rules.length > 1);
    if (emptyRule) errs.rules = "Remove or fill in every rule row — empty rows are ignored but confusing.";
    setFieldErrors(errs);
    if (Object.keys(errs).length) return;

    const body = {
      title: form.title.trim(),
      description: form.description.trim(),
      deadline: form.deadline ? `${form.deadline}T23:59:59` : null,
      quota: form.quota ? Number(form.quota) : null,
      amount: Number(form.amount) || 0,
      interests,
      rules: filled.map(({ rule_type, value, strict_or_flexible }) => ({ rule_type, value: value.trim(), strict_or_flexible })),
    };
    setSaving(true);
    try {
      await api("/api/admin/surveys", { method: "POST", body, role: "admin" });
      toast(`Survey "${body.title}" created`);
      setForm({ title: "", description: "", deadline: "", quota: "", amount: "0", interests: "" });
      setRules([{ key: ++ruleKey, rule_type: "age", value: "", strict_or_flexible: "strict" }]);
      setSuggestNote("");
      load();
    } catch (err) {
      setFormError(err.message);
      setFieldErrors((fe) => ({
        ...fe,
        deadline: err.message.toLowerCase().includes("deadline") ? err.message : fe.deadline,
      }));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Surveys" description="Create studies with eligibility rules — Strict rejects, Flexible waitlists." />

      <Card>
        <h2 className="mb-3 text-base font-semibold">New survey</h2>
        <form onSubmit={submit} noValidate className="space-y-4">
          {formError && <InlineError message={formError} />}
          <Field label="Title" error={fieldErrors.title} required id="s-title">
            <Input id="s-title" value={form.title} error={fieldErrors.title} onChange={set("title")} placeholder="e.g. Zomato Dining Habits" />
          </Field>
          <Field label="Topics / description" id="s-desc" hint="A short summary shown to members.">
            <Input id="s-desc" value={form.description} onChange={set("description")} placeholder="food dining delivery" />
          </Field>
          <Field
            label="Interests"
            id="s-interests"
            error={fieldErrors.interests}
            hint="Comma separated, e.g. food, tech. Matching surveys are highlighted for members (max 10 tags)."
          >
            <Input
              id="s-interests"
              value={form.interests}
              error={fieldErrors.interests}
              onChange={set("interests")}
              placeholder="food, tech"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Deadline" id="s-deadline" error={fieldErrors.deadline} hint={`Surveys run for at most ${CYCLE_DAYS} days.`}>
              <Input id="s-deadline" type="date" value={form.deadline} error={fieldErrors.deadline} max={deadlineMax()} onChange={set("deadline")} />
            </Field>
            <Field label="Quota" id="s-quota" error={fieldErrors.quota} hint="Blank = unlimited">
              <Input id="s-quota" type="number" min="1" value={form.quota} error={fieldErrors.quota} onChange={set("quota")} placeholder="50" />
            </Field>
            <Field label="Pay (₹)" id="s-amount" error={fieldErrors.amount}>
              <Input id="s-amount" type="number" min="0" step="1" value={form.amount} error={fieldErrors.amount} onChange={set("amount")} />
            </Field>
          </div>

          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">Eligibility rules</h3>
              <Button variant="secondary" onClick={suggest} loading={suggesting} disabled={suggesting}>
                Suggest rules
              </Button>
            </div>
            {suggestNote && (
              <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                {suggestNote} Nothing has been saved yet — press <b>Create survey</b> when you are happy with them.
              </p>
            )}
            <div className="space-y-2">
              {rules.map((r, i) => (
                <RuleRow
                  key={r.key}
                  rule={r}
                  onChange={(next) => setRules((rs) => rs.map((x, j) => (j === i ? next : x)))}
                  onRemove={() => setRules((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : rs))}
                />
              ))}
            </div>
            {fieldErrors.rules && <p role="alert" className="mt-1 text-xs text-rose-600">{fieldErrors.rules}</p>}
            <Button variant="secondary" className="mt-2" onClick={() => setRules((rs) => [...rs, { key: ++ruleKey, rule_type: "city", value: "", strict_or_flexible: "flexible" }])}>
              + Add rule
            </Button>
          </div>

          <Button type="submit" loading={saving}>
            Create survey
          </Button>
        </form>
      </Card>

      {error && rows?.length ? <RefreshBanner onRetry={load} /> : null}

      <Card className="!p-0">
        <h2 className="px-4 pt-4 text-base font-semibold sm:px-5">All surveys</h2>
        <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
          {loading && !rows ? (
            <LoadingCard label="Loading surveys…" />
          ) : error && !rows?.length ? (
            <ErrorState message={error} onRetry={load} />
          ) : rows?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Title</Th>
                  <Th>Status</Th>
                  <Th>Deadline</Th>
                  <Th>Quota</Th>
                  <Th>Done</Th>
                  <Th>Pay</Th>
                  <Th>Interests</Th>
                  <Th>Rules</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <Td className="font-medium">{s.title}</Td>
                    <Td>
                      <Tag tone={s.status === "live" ? "emerald" : "slate"}>{s.status}</Tag>
                    </Td>
                    <Td>{s.deadline || "—"}</Td>
                    <Td>{s.quota ?? "∞"}</Td>
                    <Td>
                      {s.completions}
                      {s.quota ? ` / ${s.quota}` : ""}
                    </Td>
                    <Td className="font-medium">₹{money(s.amount)}</Td>
                    <Td className="max-w-48 whitespace-normal">
                      <div className="flex flex-wrap gap-1">
                        {s.interests?.length ? (
                          s.interests.map((tag) => (
                            <Tag key={tag} tone="indigo">{tag}</Tag>
                          ))
                        ) : (
                          <span className="text-xs text-slate-500">Any interest</span>
                        )}
                      </div>
                    </Td>
                    <Td className="max-w-64 whitespace-normal">
                      <div className="flex flex-wrap gap-1">
                        {s.rules.length ? (
                          s.rules.map((r, i) => (
                            <Tag key={i} tone={r.strict_or_flexible === "strict" ? "rose" : "amber"}>
                              {r.rule_type}: {r.value} ({r.strict_or_flexible})
                            </Tag>
                          ))
                        ) : (
                          <span className="text-xs text-slate-500">No rules — open to all</span>
                        )}
                      </div>
                    </Td>
                    <Td>
                      <Button variant="secondary" onClick={() => openEdit(s)}>Edit</Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title="No surveys yet" description="Create the first one above." />
          )}
        </div>
      </Card>

      <Modal open={editing !== null} onClose={() => setEditing(null)} title="Edit survey">
        {editError && <InlineError message={editError} />}
        <form onSubmit={saveEdit} noValidate className="space-y-4">
          <Field label="Status" id="e-status">
            <Select id="e-status" value={editForm.status} onChange={setEdit("status")}>
              <option value="live">Live</option>
              <option value="draft">Draft</option>
              <option value="closed">Closed</option>
            </Select>
          </Field>
          <Field label="Deadline" id="e-deadline" error={editFieldErrors.deadline} hint={`Surveys run for at most ${CYCLE_DAYS} days from launch.`}>
            <Input id="e-deadline" type="date" value={editForm.deadline} error={editFieldErrors.deadline} max={deadlineMax()} onChange={setEdit("deadline")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Quota" id="e-quota" error={editFieldErrors.quota} hint="Blank = unlimited">
              <Input id="e-quota" type="number" min="1" value={editForm.quota} error={editFieldErrors.quota} onChange={setEdit("quota")} />
            </Field>
            <Field label="Pay (₹)" id="e-amount" error={editFieldErrors.amount}>
              <Input id="e-amount" type="number" min="0" step="1" value={editForm.amount} error={editFieldErrors.amount} onChange={setEdit("amount")} />
            </Field>
          </div>
          <Field
            label="Interests"
            id="e-interests"
            error={editFieldErrors.interests}
            hint="Comma separated, e.g. food, tech. Matching surveys are highlighted for members."
          >
            <Input
              id="e-interests"
              value={editForm.interests}
              error={editFieldErrors.interests}
              onChange={setEdit("interests")}
              placeholder="food, tech"
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={savingEdit} disabled={savingEdit}>Save changes</Button>
            <Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
