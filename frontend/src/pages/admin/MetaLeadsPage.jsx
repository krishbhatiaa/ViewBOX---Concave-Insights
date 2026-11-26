import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import RefreshBanner from "../RefreshBanner.jsx";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingCard,
  PageHeader,
  StatCard,
  Table,
  Tag,
  Td,
  Th,
} from "../../components/ui.jsx";

export default function MetaLeadsPage() {
  const [leads, setLeads] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [l, s] = await Promise.all([
        api("/api/admin/meta-leads", { role: "admin" }),
        api("/api/admin/meta-leads/stats", { role: "admin" }),
      ]);
      setLeads(l);
      setStats(s);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Meta leads"
        description="Leads from POST /api/meta/lead, grouped by campaign and ad."
      />

      {error && leads?.length ? <RefreshBanner onRetry={load} /> : null}

      {loading && !leads ? (
        <LoadingCard label="Loading Meta leads…" />
      ) : error && !leads?.length ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Total leads" value={stats?.total?.leads ?? 0} tone="indigo" />
            <StatCard label="Linked to a member" value={stats?.total?.linked ?? 0} tone="emerald" />
            <StatCard label="Needs review" value={stats?.total?.needs_review ?? 0} tone="amber" />
          </div>

          <Card className="!p-0">
            <h2 className="px-4 pt-4 text-base font-semibold sm:px-5">Per-campaign breakdown</h2>
            <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
              {stats?.by_campaign?.length ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>Campaign</Th>
                      <Th>Leads</Th>
                      <Th>Linked</Th>
                      <Th>Needs review</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.by_campaign.map((c) => (
                      <tr key={c.campaign_id}>
                        <Td className="font-medium">{c.campaign_id}</Td>
                        <Td className="tabular-nums">{c.leads}</Td>
                        <Td className="tabular-nums">{c.linked}</Td>
                        <Td className="tabular-nums">{c.needs_review}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState
                  title="No leads yet"
                  description="POST a lead to /api/meta/lead (see README §7) and it will appear here."
                />
              )}
            </div>
          </Card>

          <Card className="!p-0">
            <h2 className="px-4 pt-4 text-base font-semibold sm:px-5">All leads</h2>
            <div className="mt-3 px-4 pb-4 sm:px-5 sm:pb-5">
              {leads?.length ? (
                <Table>
                  <thead>
                    <tr>
                      <Th>Lead ID</Th>
                      <Th>Campaign</Th>
                      <Th>Ad</Th>
                      <Th>Member</Th>
                      <Th>Status</Th>
                      <Th>Received</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((l) => (
                      <tr key={l.id}>
                        <Td className="font-medium">{l.lead_id}</Td>
                        <Td>{l.campaign_id || "—"}</Td>
                        <Td>{l.ad_id || "—"}</Td>
                        <Td>{l.member ? `${l.member} (#${l.member_id})` : "—"}</Td>
                        <Td>
                          <Tag tone={l.status === "linked" ? "emerald" : "amber"}>{l.status}</Tag>
                        </Td>
                        <Td className="whitespace-nowrap text-slate-500 dark:text-slate-400">
                          {l.received_at.slice(0, 16).replace("T", " ")}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState title="No leads yet" description="Leads appear as soon as the endpoint receives one." />
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
