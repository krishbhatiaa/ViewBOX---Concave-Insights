import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import { Button, Card, Field, InlineError, Input, PageHeader } from "../../components/ui.jsx";

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
    <div className="mx-auto max-w-md px-4 py-12">
      <PageHeader title="Admin console" description="Sign in with your ops account." />
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
      <p className="mt-4 text-center text-xs text-slate-500">
        Demo: admin@concave.test / admin123 ·{" "}
        <a href="/login" className="font-medium text-indigo-600 underline dark:text-indigo-400">
          Member portal
        </a>
      </p>
    </div>
  );
}
