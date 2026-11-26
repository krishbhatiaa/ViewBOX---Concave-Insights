import { useState } from "react";
import { Button, Card, PageHeader } from "../components/ui.jsx";

const SAMPLES = {
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
};

const pretty = (payload) => JSON.stringify(payload, null, 2);

export default function MetaSimulator() {
  const [text, setText] = useState(() => pretty(SAMPLES.valid));
  const [result, setResult] = useState(null);
  const [sending, setSending] = useState(false);

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

  return (
    <div className="space-y-5">
      <PageHeader title="Meta webhook simulator" description="Send a lead payload without curl or a Meta account." />

      <Card className="space-y-3">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          In production, Meta sends only IDs; your server would call the Graph API to fetch field_data.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setText(pretty(SAMPLES.valid))}>Valid lead</Button>
          <Button variant="secondary" onClick={() => setText(pretty(SAMPLES.duplicate))}>Duplicate lead</Button>
          <Button variant="secondary" onClick={() => setText(pretty(SAMPLES.missingPhone))}>Missing phone</Button>
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
        <div>
          <Button loading={sending} onClick={send}>Send webhook</Button>
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
