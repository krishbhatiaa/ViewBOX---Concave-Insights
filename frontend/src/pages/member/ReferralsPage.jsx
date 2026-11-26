import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import {
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

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !rows) return <LoadingCard label="Loading referrals…" />;
  if (error && !rows) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="My referrals"
        description="Track every friend you invited — their stage and your bonus, so you never need to call the team."
      />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Your personal link</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">Share it anywhere — the bonus lands when a friend completes a survey.</p>
          </div>
          <CopyButton value={link} label="Copy link" />
        </div>
        <input
          readOnly
          value={link}
          aria-label="Your referral link"
          onFocus={(e) => e.target.select()}
          className="mt-3 min-h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
        />
      </Card>

      {rows.length ? (
        <Card className="!p-0">
          <div className="flex items-center justify-between px-4 pt-4 sm:px-5">
            <h2 className="text-base font-semibold">Friends invited</h2>
            <span className="text-sm text-slate-500 dark:text-slate-400">{rows.length} total</span>
          </div>
          <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
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
                  <tr key={r.friend + r.updated_at}>
                    <Td className="font-medium">{r.friend}</Td>
                    <Td className="tabular-nums">{r.phone}</Td>
                    <Td>
                      <StageTag stage={r.stage} />
                    </Td>
                    <Td>
                      {r.bonus ? (
                        <span>
                          ₹{r.bonus.amount} · <StageTag stage={r.bonus.status} />{" "}
                          <span className="text-xs text-slate-500 dark:text-slate-400">{PAYOUT_LABEL[r.bonus.status] || r.bonus.status}</span>
                        </span>
                      ) : r.stage === "Completed" ? (
                        "—"
                      ) : (
                        "—"
                      )}
                    </Td>
                    <Td className="max-w-48 whitespace-normal text-slate-500 dark:text-slate-400">
                      {r.failure_reason || (STAGE_EXPLANATION[r.stage] && <p>{STAGE_EXPLANATION[r.stage]}</p>)}
                    </Td>
                    <Td className="text-slate-500 dark:text-slate-400">{r.updated_at.slice(0, 10)}</Td>
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
