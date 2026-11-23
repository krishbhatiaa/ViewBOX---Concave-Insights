import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import { Button, Card, Field, InlineError, Input, PageHeader } from "../../components/ui.jsx";
import { getLinkParams, setPending } from "../../lib/auth.js";

export default function PhonePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [demoOtp, setDemoOtp] = useState("");
  const [isMember, setIsMember] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [loading, setLoading] = useState(false);

  const validPhone = (p) => /^[6-9]\d{9}$/.test(p);

  async function sendOtp(e) {
    e?.preventDefault();
    setError("");
    if (!validPhone(phone)) {
      setFieldError("Enter a valid 10-digit Indian mobile number (starts with 6-9).");
      return;
    }
    setFieldError("");
    setLoading(true);
    try {
      const r = await api("/api/otp/request", { method: "POST", body: { phone } });
      setIsMember(r.is_member);
      setDemoOtp(r.otp);
      setOtp(r.otp);
      setStep("otp");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function verify(e) {
    e?.preventDefault();
    setError("");
    if (!/^\d{6}$/.test(otp)) {
      setError("Enter the 6-digit OTP.");
      return;
    }
    setLoading(true);
    try {
      if (isMember) {
        const r = await api("/api/login", { method: "POST", body: { phone, otp } });
        tokens.set(true, r.token);
        navigate("/home", { replace: true });
      } else {
        setPending({ phone, otp });
        navigate("/profile", { replace: true });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const params = getLinkParams();

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <PageHeader title="Welcome to ViewBox" description="Log in or join with your mobile number." />
      <Card>
        {params.src || params.ref ? (
          <p className="mb-3 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
            You arrived through a special link — we will use it when you sign up.
          </p>
        ) : null}

        {step === "phone" ? (
          <form onSubmit={sendOtp} noValidate>
            <Field label="Mobile number" error={fieldError} required id="phone">
              <Input
                id="phone"
                inputMode="numeric"
                autoComplete="tel-national"
                maxLength={10}
                placeholder="10-digit mobile"
                value={phone}
                error={fieldError}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
              />
            </Field>
            {error && <div className="mt-3"><InlineError message={error} /></div>}
            <Button type="submit" loading={loading} className="mt-4 w-full">
              Send OTP
            </Button>
          </form>
        ) : (
          <form onSubmit={verify} noValidate>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Demo mode: your OTP is shown here — no SMS is sent.
            </p>
            <p
              className="my-3 rounded-lg border border-dashed border-slate-300 py-3 text-center text-3xl font-bold tracking-[0.3em] dark:border-slate-600"
              aria-label="Your OTP"
            >
              {demoOtp}
            </p>
            <Field label="OTP" required id="otp" hint="It expires in 5 minutes.">
              <Input
                id="otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="Enter OTP"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
              />
            </Field>
            {error && <div className="mt-3"><InlineError message={error} /></div>}
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <Button type="submit" loading={loading} className="flex-1">
                Continue
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setStep("phone");
                  setError("");
                }}
              >
                Change number
              </Button>
            </div>
          </form>
        )}
      </Card>
      <p className="mt-4 text-center text-xs text-slate-500">
        Demo members: 9000000001–9000000007 · Admin is at{" "}
        <a href="/admin" className="font-medium text-indigo-600 underline dark:text-indigo-400">
          /admin
        </a>
      </p>
    </div>
  );
}
