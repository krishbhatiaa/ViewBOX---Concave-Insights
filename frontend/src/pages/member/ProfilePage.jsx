import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import { Button, Card, Field, InlineError, Input, PageHeader, Select, Skeleton } from "../../components/ui.jsx";
import { clearLinkParams, clearPending, getLinkParams, getPending } from "../../lib/auth.js";
import { GENDER_OPTIONS, INCOME_OPTIONS } from "../../lib/stages.js";

export default function ProfilePage() {
  const navigate = useNavigate();
  const pending = getPending();
  const [resolve, setResolve] = useState({ source: null, referrer: null, needs_fallback: true });
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState({
    name: "",
    dob: "",
    gender: "",
    city: "",
    income_range: "",
    interests: "",
    referrer_phone: "",
    how_heard_source_id: "",
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resolveLoading, setResolveLoading] = useState(true);
  const [resolveError, setResolveError] = useState("");

  useEffect(() => {
    if (!pending) return;
    const params = getLinkParams();
    let alive = true;
    (async () => {
      try {
        const r = await api(
          `/api/links/resolve?src=${encodeURIComponent(params.src)}&ref=${encodeURIComponent(params.ref)}`
        );
        if (!alive) return;
        setResolve(r);
        if (r.needs_fallback) {
          const list = await api("/api/sources/public");
          if (alive) setSources(list);
        }
      } catch (err) {
        if (!alive) return;
        setResolve({ source: null, referrer: null, needs_fallback: true });
        setResolveError(err.message || "We could not check your invite link — you can still continue below.");
        try {
          const list = await api("/api/sources/public");
          if (alive) setSources(list);
        } catch {
          /* fallback list is optional; the form still works */
        }
      } finally {
        if (alive) setResolveLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [pending]);

  if (!pending) return <Navigate to="/login" replace />;

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  function validate() {
    const errs = {};
    if (form.name.trim().length < 2) errs.name = "Please enter your full name (at least 2 characters).";
    if (!form.dob) errs.dob = "Date of birth is required so we can check age limits.";
    else {
      const age = (Date.now() - new Date(form.dob).getTime()) / (365.25 * 24 * 3600 * 1000);
      if (age < 13) errs.dob = "You must be at least 13 years old to join.";
      if (age > 100) errs.dob = "Please check the date of birth — that looks too far in the past.";
    }
    if (!form.gender) errs.gender = "Please choose a gender.";
    if (form.city.trim().length < 2) errs.city = "Please enter your city.";
    if (!form.income_range) errs.income_range = "Please choose an income range.";
    if (form.referrer_phone && !/^[6-9]\d{9}$/.test(form.referrer_phone.replace(/\D/g, "").slice(-10)))
      errs.referrer_phone = "Enter a valid 10-digit mobile number, or leave it blank.";
    return errs;
  }

  async function submit(e) {
    e.preventDefault();
    setFormError("");
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;

    const params = getLinkParams();
    const body = {
      phone: pending.phone,
      otp: pending.otp,
      name: form.name.trim(),
      dob: form.dob,
      gender: form.gender,
      city: form.city.trim(),
      income_range: form.income_range,
      interests: form.interests.split(",").map((x) => x.trim()).filter(Boolean),
      src: params.src || null,
      ref: params.ref || null,
      first_src: params.first || null,
      referrer_phone: form.referrer_phone || null,
      how_heard_source_id: form.how_heard_source_id ? Number(form.how_heard_source_id) : null,
    };
    setLoading(true);
    try {
      const r = await api("/api/signup", { method: "POST", body });
      tokens.set(true, r.token);
      clearPending();
      clearLinkParams();
      navigate("/home", { replace: true });
    } catch (err) {
      setFormError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <PageHeader
        title="Tell us about you"
        description="Your profile is filled once, right after your first login. It decides which surveys you qualify for."
      />
      <Card>
        {resolveLoading ? (
          <div className="mb-3 space-y-2" role="status" aria-label="Checking your link">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : resolveError ? (
          <div className="mb-3">
            <InlineError message={resolveError} />
          </div>
        ) : resolve.source ? (
          <p className="mb-3 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            You were invited via <b>{resolve.source}</b>
          </p>
        ) : resolve.referrer ? (
          <p className="mb-3 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            Invited by <b>{resolve.referrer}</b>
          </p>
        ) : null}

        <form onSubmit={submit} noValidate className="space-y-4">
          {formError && <InlineError message={formError} />}

          <Field label="Full name" error={errors.name} required id="name">
            <Input id="name" autoComplete="name" value={form.name} error={errors.name} onChange={set("name")} placeholder="e.g. Asha Rao" />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date of birth" error={errors.dob} required id="dob">
              <Input id="dob" type="date" value={form.dob} error={errors.dob} onChange={set("dob")} max={new Date().toISOString().slice(0, 10)} />
            </Field>
            <Field label="Gender" error={errors.gender} required id="gender">
              <Select id="gender" value={form.gender} error={errors.gender} onChange={set("gender")}>
                <option value="">Select…</option>
                {GENDER_OPTIONS.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </Select>
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="City" error={errors.city} required id="city">
              <Input id="city" autoComplete="address-level2" value={form.city} error={errors.city} onChange={set("city")} placeholder="e.g. Mumbai" />
            </Field>
            <Field label="Income range" error={errors.income_range} required id="income">
              <Select id="income" value={form.income_range} error={errors.income_range} onChange={set("income_range")}>
                <option value="">Select…</option>
                {INCOME_OPTIONS.map((i) => (
                  <option key={i}>{i}</option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label="Interests" id="interests" hint="Comma separated — e.g. food, tech, fashion">
            <Input id="interests" value={form.interests} onChange={set("interests")} placeholder="food, tech" />
          </Field>

          {resolve.needs_fallback && (
            <Field label="How did you hear about us?" id="how" required>
              <Select id="how" value={form.how_heard_source_id} onChange={set("how_heard_source_id")}>
                <option value="">Select…</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {!getLinkParams().ref && (
            <Field label="Referrer's mobile number" id="rph" error={errors.referrer_phone} hint="Optional — the number of the friend who invited you.">
              <Input
                id="rph"
                inputMode="numeric"
                maxLength={11}
                value={form.referrer_phone}
                error={errors.referrer_phone}
                onChange={set("referrer_phone")}
                placeholder="10-digit mobile"
              />
            </Field>
          )}

          <Button type="submit" loading={loading} className="w-full">
            Create my account
          </Button>
        </form>
      </Card>
    </div>
  );
}
