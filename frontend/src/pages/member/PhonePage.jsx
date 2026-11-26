import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, tokens } from "../../api.js";
import { AuthShell, Button, Card, Field, InlineError, Input } from "../../components/ui.jsx";
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
    <AuthShell
      eyebrow="Member portal / secure access"
      title={<>Real people.<br />Useful evidence.</>}
      description="Join the ViewBox research panel with your mobile number."
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[2px] border border-line-2 bg-paper-2 px-3 py-2 font-mono text-xs text-ink-2">
          <span>
            <span className="mr-2 border border-line-2 bg-paper-3 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink">
              DEMO
            </span>
            Members: 9000000001–9000000007
          </span>
          <a href="/admin" className="font-semibold text-acc underline">
            /admin
          </a>
        </div>
      }
    >
      <Card>
        {params.src || params.ref ? (
          <p className="mb-3 rounded-[2px] border border-l-4 border-deep bg-deep/10 px-3 py-2 font-mono text-xs text-ink-2">
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
            <p className="font-mono text-xs uppercase tracking-wide text-ink-3">
              Demo mode: your OTP is shown here — no SMS is sent.
            </p>
            <p
              className="my-3 rounded-[2px] border border-dashed border-line-2 bg-paper-3 py-3 text-center font-mono text-3xl tracking-[0.3em] text-ink"
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
    </AuthShell>
  );
}
