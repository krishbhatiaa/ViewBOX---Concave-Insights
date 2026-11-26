import { useCallback, useEffect, useState } from "react";
import { api, downloadBlob, money } from "../../api.js";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Button,
  Card,
  CopyButton,
  EmptyState,
  ErrorState,
  LoadingCard,
  PageHeader,
  StageTag,
  Table,
  Td,
  Th,
} from "../../components/ui.jsx";
import { PAYOUT_LABEL, STAGE_EXPLANATION } from "../../lib/stages.js";

export default function ReferralsPage() {
  const [rows, setRows] = useState(null);
  const [link, setLink] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [qrLoading, setQrLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [referrals, me] = await Promise.all([
        api("/api/me/referrals", { role: "member" }),
        api("/api/me", { role: "member" }),
      ]);
      setRows(referrals);
      setLink(me.referral_link);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const downloadQr = async () => {
    setQrLoading(true);
    try {
      const blob = await api("/api/me/referral-qr", { role: "member", raw: true });
      downloadBlob(blob, "viewbox-referral-qr.png");
    } catch (err) {
      setError(err.message);
    } finally {
      setQrLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !rows) return <LoadingCard label="Loading referrals…" />;
  if (error && !rows) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return null;

  return (
    <div className="space-y-5">
      {error && rows ? <RefreshBanner onRetry={load} /> : null}
      <PageHeader
        kicker="MEMBER / REFERRALS"
        title="My referrals"
        description="Track every friend you invited — their stage and your bonus, so you never need to call the team."
      />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">01 / Your personal link</h2>
            <p className="mt-1 text-sm text-ink-2">Share it anywhere — the bonus lands when a friend completes a survey.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <CopyButton value={link} label="Copy link" />
            <Button variant="secondary" loading={qrLoading} onClick={downloadQr}>Download QR</Button>
          </div>
        </div>
        <input
          readOnly
          value={link}
          aria-label="Your referral link"
          onFocus={(e) => e.target.select()}
          className="mt-3 min-h-11 w-full rounded-[2px] border border-line-2 bg-paper px-3 font-mono text-xs text-ink-2"
        />
      </Card>

      {rows.length ? (
        <Card className="!p-0">
          <div className="flex items-center justify-between border-b border-line px-4 py-3 sm:px-5">
            <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">02 / Friends invited</h2>
            <span className="font-mono text-xs tabular-nums text-ink-2">{rows.length} total</span>
          </div>
          <div className="px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
            <Table>
              <thead>
                <tr>
                  <Th>Friend</Th>
                  <Th>Phone</Th>
                  <Th>Stage</Th>
                  <Th>Bonus</Th>
                  <Th>Note</Th>
                  <Th>Updated</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.friend + r.updated_at} className="hover:bg-paper-2">
                    <Td className="font-medium">{r.friend}</Td>
                    <Td className="font-mono text-xs tabular-nums text-ink-2">{r.phone}</Td>
                    <Td>
                      <StageTag stage={r.stage} />
                    </Td>
                    <Td className="font-mono text-xs tabular-nums">
                      {r.bonus ? (
                        <span>
                          ₹{money(r.bonus.amount)} · <StageTag stage={r.bonus.status} />{" "}
                          <span className="text-ink-2">{PAYOUT_LABEL[r.bonus.status] || r.bonus.status}</span>
                          {r.bonus.utr && (
                            <span className="mt-0.5 block font-mono text-[10px] text-ink-2">UTR {r.bonus.utr}</span>
                          )}
                        </span>
                      ) : r.stage === "Completed" ? (
                        "—"
                      ) : (
                        "—"
                      )}
                    </Td>
                    <Td className="max-w-48 whitespace-normal text-sm text-ink-2">
                      {r.failure_reason || (STAGE_EXPLANATION[r.stage] && <p>{STAGE_EXPLANATION[r.stage]}</p>)}
                    </Td>
                    <Td className="font-mono text-xs tabular-nums text-ink-2">{r.updated_at.slice(0, 10)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="No friends invited yet"
          description="Share your link above — you will see each friend's progress here."
        />
      )}
    </div>
  );
}
