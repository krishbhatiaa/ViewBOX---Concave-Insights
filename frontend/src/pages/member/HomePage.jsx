import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../api.js";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Card,
  CopyButton,
  EmptyState,
  ErrorState,
  LoadingCard,
  PageHeader,
  StageTag,
  Table,
  Tag,
  Td,
  Th,
} from "../../components/ui.jsx";
import { PAYOUT_LABEL, STAGE_EXPLANATION } from "../../lib/stages.js";

function StatusPanel({ status }) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">Your status</h2>
        <StageTag stage={status.stage} />
      </div>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{STAGE_EXPLANATION[status.stage] || ""}</p>
      {status.failure_reason && (
        <p className="mt-2 text-sm text-slate-500">Reason: {status.failure_reason}</p>
      )}

      {status.completions.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">Completions</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-slate-600 dark:text-slate-300">
            {status.completions.map((c, i) => (
              <li key={i}>
                {c.survey} on {c.completed_at}
                {!c.quality_passed && <span className="text-rose-600"> (quality check failed)</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4">
        <h3 className="text-sm font-semibold">Earnings</h3>
        {status.payouts.length ? (
          <Table className="mt-2">
            <thead>
              <tr>
                <Th>Earning</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {status.payouts.map((p, i) => (
                <tr key={i}>
                  <Td>{p.kind}</Td>
                  <Td className="font-medium">₹{money(p.amount)}</Td>
                  <Td>
                    <StageTag stage={p.status} />
                    <span className="ml-2 text-xs text-slate-500">{PAYOUT_LABEL[p.status] || p.status}</span>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <p className="mt-1 text-sm text-slate-500">No earnings yet.</p>
        )}
      </div>
    </Card>
  );
}

function SurveyCard({ survey }) {
  const tone =
    survey.result === "Approved" ? "emerald" : survey.result === "Waitlisted" ? "amber" : "rose";
  return (
    <Card
      className={
        survey.matches_interests
          ? "!border-indigo-300 ring-1 ring-indigo-200 dark:!border-indigo-800 dark:ring-indigo-900"
          : ""
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-semibold">{survey.title}</h3>
        <Tag tone={tone}>{survey.result}</Tag>
      </div>
      {survey.matches_interests && (
        <span className="mt-1 inline-block">
          <Tag tone="indigo">Matches your interests</Tag>
        </span>
      )}
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        {survey.description}
        {survey.amount ? ` · ₹${money(survey.amount)}` : ""}
        {survey.deadline ? ` · closes ${survey.deadline.slice(0, 10)}` : ""}
      </p>
      <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">{survey.reason}</p>
    </Card>
  );
}

export default function HomePage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [me, surveys, referrals, status] = await Promise.all([
        api("/api/me", { role: "member" }),
        api("/api/surveys", { role: "member" }),
        api("/api/me/referrals", { role: "member" }),
        api("/api/me/status", { role: "member" }),
      ]);
      setData({ me, surveys, referrals, status });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !data) return <LoadingCard label="Loading your dashboard…" />;
  if (error && !data) return <ErrorState message={error} onRetry={load} />;
  if (!data) return null;

  const { me, surveys, referrals, status } = data;
  const completedFriends = referrals.filter((r) => r.stage === "Completed").length;

  return (
    <div className="space-y-5">
      {error && data ? <RefreshBanner onRetry={load} /> : null}
      <PageHeader
        title={`Hi ${me.name}`}
        description={`${me.phone} · ${me.city || "—"}${referrals.length ? ` · ${referrals.length} friend${referrals.length > 1 ? "s" : ""} invited (${completedFriends} completed)` : ""}`}
      />

      {me.next_eligible_date && (
        <div
          role="status"
          className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
        >
          Cool-off active: you can join new surveys again on <b>{me.next_eligible_date}</b>.
        </div>
      )}

      <StatusPanel status={status} />

      <section>
        <h2 className="mb-3 text-base font-semibold">Live surveys</h2>
        {loading ? (
          <div className="space-y-3">
            <LoadingCard />
            <LoadingCard />
          </div>
        ) : surveys.length ? (
          <div className="space-y-3">
            {surveys.map((s) => (
              <SurveyCard key={s.id} survey={s} />
            ))}
          </div>
        ) : (
          <EmptyState title="No live surveys right now" description="Check back soon — new studies are added regularly." />
        )}
      </section>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Invite friends</h2>
            <p className="text-sm text-slate-500">
              You earn a bonus when a friend completes a survey. See{" "}
              <a href="/referrals" className="font-medium text-indigo-600 underline dark:text-indigo-400">
                all referrals
              </a>
              .
            </p>
          </div>
          <CopyButton value={me.referral_link} label="Copy referral link" />
        </div>
        <input
          readOnly
          value={me.referral_link}
          aria-label="Your referral link"
          onFocus={(e) => e.target.select()}
          className="mt-3 min-h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300"
        />
      </Card>
    </div>
  );
}
