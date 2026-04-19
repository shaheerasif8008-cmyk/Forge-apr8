"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { resolveApiBaseUrl } from "@/app/config";
import type { MetricsDashboard } from "@/components/types";
import { fetchMetricsDashboard } from "@/lib/api";

const PIE_COLORS = ["#2d6a4f", "#c0843d", "#ba5a31", "#4c5c43"];

export default function MetricsPage() {
  const apiBase = resolveApiBaseUrl();
  const [dashboard, setDashboard] = useState<MetricsDashboard | null>(null);

  useEffect(() => {
    void fetchMetricsDashboard(apiBase).then(setDashboard);
  }, [apiBase]);

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <div className="rounded-[32px] border border-ink/10 bg-white/80 p-6 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Metrics Dashboard</div>
            <h1 className="mt-2 font-display text-4xl text-ink">Operational telemetry for the deployed employee.</h1>
          </div>
          <Link className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white" href="/">
            Back to Conversation
          </Link>
        </div>

        {!dashboard ? (
          <div className="mt-8 rounded-[24px] bg-paper/45 p-8 text-center text-ink/60">Loading metrics…</div>
        ) : (
          <>
            <div className="mt-6 grid gap-4 md:grid-cols-4">
              <MetricCard label="Tasks Completed" value={String(dashboard.kpis.tasks_total)} />
              <MetricCard label="Average Confidence" value={dashboard.kpis.avg_confidence.toFixed(2)} />
              <MetricCard label="Pending Approvals" value={String(dashboard.kpis.pending_approvals)} />
              <MetricCard label="Avg Duration (s)" value={dashboard.kpis.avg_duration_seconds.toFixed(1)} />
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <ChartCard title="Tasks by Day">
                <ResponsiveContainer height={280} width="100%">
                  <LineChart data={dashboard.tasks_by_day}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d8d0c6" />
                    <XAxis dataKey="date" tick={{ fill: "#5f5a54", fontSize: 12 }} />
                    <YAxis tick={{ fill: "#5f5a54", fontSize: 12 }} />
                    <Tooltip />
                    <Line dataKey="tasks" stroke="#2d6a4f" strokeWidth={3} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard title="Approval Mix">
                <ResponsiveContainer height={280} width="100%">
                  <PieChart>
                    <Pie
                      cx="50%"
                      cy="50%"
                      data={dashboard.approval_mix}
                      dataKey="value"
                      innerRadius={64}
                      outerRadius={92}
                      nameKey="name"
                      paddingAngle={3}
                    >
                      {dashboard.approval_mix.map((entry, index) => (
                        <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard title="Activity Categories">
                <ResponsiveContainer height={280} width="100%">
                  <BarChart data={dashboard.activity_mix}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d8d0c6" />
                    <XAxis dataKey="name" tick={{ fill: "#5f5a54", fontSize: 12 }} />
                    <YAxis tick={{ fill: "#5f5a54", fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="value" fill="#c0843d" radius={[10, 10, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard title="Confidence Trend">
                <ResponsiveContainer height={280} width="100%">
                  <LineChart data={dashboard.confidence_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d8d0c6" />
                    <XAxis dataKey="label" hide />
                    <YAxis domain={[0, 1]} tick={{ fill: "#5f5a54", fontSize: 12 }} />
                    <Tooltip />
                    <Line dataKey="confidence" stroke="#ba5a31" strokeWidth={3} type="monotone" />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[24px] border border-ink/10 bg-paper/45 p-5">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</div>
      <div className="mt-3 font-display text-4xl text-ink">{value}</div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[28px] border border-ink/10 bg-white/90 p-5 shadow-card">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{title}</div>
      <div className="mt-4">{children}</div>
    </section>
  );
}
