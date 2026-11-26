import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import { AuthShell, Button, Card, Field, InlineError, Input } from "../../components/ui.jsx";

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@concave.test");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState({});
  const [loading, setLoading] = useState(false);

  if (tokens.get(false)) return <Navigate to="/admin/members" replace />;

  async function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!email.trim()) errs.email = "Email is required.";
    if (!password) errs.password = "Password is required.";
    setFieldError(errs);
    setError("");
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      const r = await api("/api/admin/login", { method: "POST", body: { email: email.trim(), password } });
      tokens.set(false, r.token);
      navigate("/admin/members", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Operations / admin console"
      title={<>Keep the panel<br />moving.</>}
      description="Review members, referrals, surveys, and payouts from one desk."
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[2px] border border-line-2 bg-paper-2 px-3 py-2 font-mono text-xs text-ink-2">
          <span>
            <span className="mr-2 border border-line-2 bg-paper-3 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink">
              DEMO
            </span>
            admin@concave.test / admin123
          </span>
          <a href="/login" className="font-semibold text-acc underline">
            Member portal
          </a>
        </div>
      }
    >
      <Card>
        <form onSubmit={submit} noValidate className="space-y-4">
          {error && <InlineError message={error} />}
          <Field label="Email" error={fieldError.email} required id="email">
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              error={fieldError.email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Password" error={fieldError.password} required id="password">
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              error={fieldError.password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="admin123"
            />
          </Field>
          <Button type="submit" loading={loading} className="w-full">
            Log in
          </Button>
        </form>
      </Card>
    </AuthShell>
  );
}
