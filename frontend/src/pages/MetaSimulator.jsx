import { useState } from "react";
import { Button, Card, Field, Input, PageHeader, Select } from "../components/ui.jsx";

const SAMPLES = {
  simple: {
    valid: {
      lead_id: "lead_demo_1001",
      form_id: "form_demo_1",
      campaign_id: "camp_demo_1",
      ad_id: "ad_demo_1",
      time: "2026-11-26T10:00:00+00:00",
      fields: {"name": "Meta Sim Person", "phone": "9960000091", "city": "Mumbai"},
    },
    duplicate: {
      lead_id: "lead_demo_1001",
      form_id: "form_demo_1",
      campaign_id: "camp_demo_1",
      ad_id: "ad_demo_1",
      time: "2026-11-26T10:05:00+00:00",
      fields: {"name": "Meta Sim Person", "phone": "9960000091", "city": "Mumbai"},
    },
    missingPhone: {
      lead_id: "lead_demo_1002",
      form_id: "form_demo_1",
      campaign_id: "camp_demo_1",
      ad_id: "ad_demo_1",
      time: "2026-11-26T10:10:00+00:00",
      fields: {"name": "No Phone Person", "city": "Mumbai"},
    },
  },
  envelope: {
    valid: {
      object: "page",
      entry: [{
        time: 1764146400,
        changes: [{
          field: "leadgen",
          value: {
            leadgen_id: "lead_demo_2001",
            form_id: "form_demo_1",
            ad_id: "ad_demo_1",
            created_time: "2026-11-26T10:00:00+00:00",
          },
        }],
      }],
    },
    duplicate: {
      object: "page",
      entry: [{
        time: 1764146700,
        changes: [{
          field: "leadgen",
          value: {
            leadgen_id: "lead_demo_2001",
            form_id: "form_demo_1",
            ad_id: "ad_demo_1",
            created_time: "2026-11-26T10:05:00+00:00",
          },
        }],
      }],
    },
    missingPhone: {
      object: "page",
      entry: [{
        time: 1764147000,
        changes: [{
          field: "leadgen",
          value: {
            leadgen_id: "lead_demo_missing-phone",
            form_id: "form_demo_1",
            ad_id: "ad_demo_1",
            created_time: "2026-11-26T10:10:00+00:00",
          },
        }],
      }],
    },
  },
};

const pretty = (payload) => JSON.stringify(payload, null, 2);

export default function MetaSimulator() {
  const [format, setFormat] = useState("simple");
  const [sample, setSample] = useState("valid");
  const [text, setText] = useState(() => pretty(SAMPLES.simple.valid));
  const [result, setResult] = useState(null);
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyToken, setVerifyToken] = useState("meta-verify-demo");
  const [challenge, setChallenge] = useState("1234567890");

  const chooseFormat = (next) => {
    setFormat(next);
    setText(pretty(SAMPLES[next][sample]));
  };

  const chooseSample = (next) => {
    setSample(next);
    setText(pretty(SAMPLES[format][next]));
  };

  const send = async () => {
    setSending(true);
    try {
      const res = await fetch("/api/meta/lead", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: text,
      });
      const body = await res.text();
      setResult({status: res.status, body});
    } catch (err) {
      setResult({status: 0, body: err.message});
    } finally {
      setSending(false);
    }
  };

  const testHandshake = async () => {
    setVerifying(true);
    try {
      const params = new URLSearchParams({
        "hub.mode": "subscribe",
        "hub.verify_token": verifyToken,
        "hub.challenge": challenge,
      });
      const res = await fetch(`/webhooks/meta?${params}`);
      const body = await res.text();
      setResult({status: res.status, body: body || "OK"});
    } catch (err) {
      setResult({status: 0, body: err.message});
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Meta webhook simulator" description="Test the verify handshake and both lead payload formats without a Meta account." />

      <Card className="space-y-4">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          In production, Meta sends only IDs in a wrapped envelope; the server fetches field_data from the Graph API. Without a page access token the mock fetcher supplies fields.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Payload format" id="meta-format" hint="Switch to the real Meta envelope or the simple dev body.">
            <Select id="meta-format" value={format} onChange={(e) => chooseFormat(e.target.value)}>
              <option value="simple">Simple dev payload</option>
              <option value="envelope">Wrapped leadgen envelope</option>
            </Select>
          </Field>
          <Field label="Verify token" id="meta-verify-token" hint="Must match META_VERIFY_TOKEN to return the challenge.">
            <Input id="meta-verify-token" value={verifyToken} onChange={(e) => setVerifyToken(e.target.value)} />
          </Field>
        </div>
        <Field label="Challenge" id="meta-challenge" hint="Meta echoes this value on a successful handshake.">
          <Input id="meta-challenge" value={challenge} onChange={(e) => setChallenge(e.target.value)} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => chooseSample("valid")}>Valid lead</Button>
          <Button variant="secondary" onClick={() => chooseSample("duplicate")}>Duplicate lead</Button>
          <Button variant="secondary" onClick={() => chooseSample("missingPhone")}>Missing phone</Button>
        </div>
        <label className="block text-sm font-medium" htmlFor="meta-payload">
          Payload
        </label>
        <textarea
          id="meta-payload"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={16}
          spellCheck={false}
          className="w-full rounded-lg border border-slate-300 bg-white p-3 font-mono text-xs text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
        <div className="flex flex-wrap gap-2">
          <Button loading={sending} onClick={send}>Send webhook</Button>
          <Button variant="secondary" loading={verifying} onClick={testHandshake}>Test handshake</Button>
        </div>
      </Card>

      <Card className="space-y-2">
        <h2 className="text-base font-semibold">Response</h2>
        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-800 dark:bg-slate-950 dark:text-slate-100">
          {result ? `Status: ${result.status}\n${result.body}` : "No response yet."}
        </pre>
      </Card>
    </div>
  );
}
