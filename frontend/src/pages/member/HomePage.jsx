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
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">01 / Status</span>
          <StageTag stage={status.stage} />
        </div>
      </div>
      <p className="text-sm text-ink-2">{STAGE_EXPLANATION[status.stage] || ""}</p>
      {status.failure_reason && (
        <p className="mt-2 font-mono text-xs text-acc">Reason: {status.failure_reason}</p>
      )}

      {status.completions.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <h3 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">Completions</h3>
          <ul className="mt-1.5 list-inside list-disc text-sm text-ink-2">
            {status.completions.map((c, i) => (
              <li key={i}>
                {c.survey} <span className="font-mono text-xs">on {c.completed_at}</span>
                {!c.quality_passed && <span className="font-mono text-xs text-acc"> (quality check failed)</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 border-t border-line pt-3">
        <h3 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">Earnings</h3>
        {status.payouts.length ? (
          <Table className="mt-2">
            <thead>
              <tr>
                <Th>Earning</Th>
                <Th>Amount</Th>
                <Th>UTR / transaction ID</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {status.payouts.map((p, i) => (
                <tr key={i} className="hover:bg-paper-2">
                  <Td>{p.kind}</Td>
                  <Td className="font-mono font-medium tabular-nums">₹{money(p.amount)}</Td>
                  <Td className="font-mono text-xs text-ink-2">{p.utr || "—"}</Td>
                  <Td>
                    <StageTag stage={p.status} />
                    <span className="ml-2 font-mono text-xs text-ink-2">{PAYOUT_LABEL[p.status] || p.status}</span>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <p className="mt-1 text-sm text-ink-2">No earnings yet.</p>
        )}
      </div>
    </Card>
  );
}

function daysLeftLabel(deadline) {
  if (!deadline) return null;
  const dateStr = deadline.slice(0, 10);
  const diff = Math.ceil((new Date(`${dateStr}T23:59:59`).getTime() - Date.now()) / 86400000);
  if (diff < 0) return `${dateStr} (closed)`;
  if (diff === 0) return `${dateStr} (due today)`;
  return `${dateStr} (${diff}d left)`;
}

function SurveyCard({ survey }) {
  const tone =
    survey.result === "Approved" ? "emerald" : survey.result === "Waitlisted" ? "amber" : "rose";
  const deadlineText = daysLeftLabel(survey.deadline);
  return (
    <Card className={survey.matches_interests ? "border-l-[3px] border-l-acc" : ""}>
      {survey.matches_interests && (
        <div className="mb-2">
          <Tag tone="match" className="gap-1.5">
            <span className="inline-block h-1.5 w-1.5 bg-acc" aria-hidden="true" />
            Matches your interests{survey.matched_interests?.length ? `: ${survey.matched_interests.join(", ")}` : ""}
          </Tag>
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-display text-2xl font-normal leading-tight text-ink">{survey.title}</h3>
        <StageTag stage={survey.result} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
        {survey.description && <span>{survey.description}</span>}
        {survey.amount ? (
          <span className="font-mono text-xs font-semibold tabular-nums text-ink">₹{money(survey.amount)}</span>
        ) : null}
        {deadlineText ? (
          <span className="font-mono text-xs tabular-nums text-ink-2">closes {deadlineText}</span>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
        <Tag tone={tone}>{survey.result}</Tag>
        <p className="text-sm text-ink-2">{survey.reason}</p>
      </div>
      {survey.google_form_url && (
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
          <a href={survey.google_form_url} target="_blank" rel="noreferrer"
             className="font-mono text-xs font-medium text-deep underline">
            Open Google Form
          </a>
          {survey.google_form_mode === "mock" && (
            <span className="font-mono text-xs text-ink-2">demo link — configure Google credentials to publish</span>
          )}
        </div>
      )}
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

  const { me, surveys, referrals, status } = data;
  const completedFriends = referrals.filter((r) => r.stage === "Completed").length;

  return (
    <div className="space-y-5">
      {error ? <RefreshBanner onRetry={load} /> : null}
      <PageHeader
        kicker="MEMBER / DASHBOARD"
        title={`Hi ${me.name}`}
        description={
          <span className="font-mono text-xs">
            {me.phone} · {me.city || "—"}
            {referrals.length ? ` · ${referrals.length} friend${referrals.length > 1 ? "s" : ""} invited (${completedFriends} completed)` : ""}
          </span>
        }
      />

      {me.next_eligible_date && (
        <div
          role="status"
          className="rounded-[2px] border border-l-4 border-line-2 border-l-acc bg-paper-2 px-4 py-3 text-sm text-ink"
        >
          Cool-off active: you can join new surveys again on <b className="font-mono">{me.next_eligible_date}</b>.
        </div>
      )}

      <StatusPanel status={status} />

      <section>
        <div className="mb-3 border-t border-line pt-3">
          <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">02 / Live surveys</h2>
        </div>
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
            <h2 className="font-mono text-[11px] uppercase tracking-[.08em] text-ink-2">03 / Invite friends</h2>
            <p className="mt-1 text-sm text-ink-2">
              You earn a bonus when a friend completes a survey. See{" "}
              <a href="/referrals" className="font-medium text-deep underline">
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
          className="mt-3 min-h-11 w-full rounded-[2px] border border-line-2 bg-paper px-3 font-mono text-xs text-ink-2"
        />
      </Card>
    </div>
  );
}
