"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { AgentWorkboard } from "@/lib/dashboard/types";
import { formatDate, formatMoney } from "@/lib/customers/format";

export function AgentWorkboardPanels({
  agent,
  currency,
  show,
}: {
  agent: AgentWorkboard;
  currency: string;
  show: {
    today: boolean;
    overdue: boolean;
    promises: boolean;
    activities: boolean;
  };
}) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {show.today ? (
        <Panel title="Bugünkü görevler" href="/collections" empty="Bugün için görev yok.">
          {agent.today_tasks.map((t) => (
            <li key={t.id} className="flex justify-between gap-2 text-sm">
              <Link href={`/customers/${t.customer_id}`} className="truncate font-medium hover:text-primary">
                {t.title || t.customer_name}
              </Link>
              <span className="shrink-0 text-muted">{t.due_date}</span>
            </li>
          ))}
        </Panel>
      ) : null}
      {show.overdue ? (
        <Panel title="Gecikmiş görevler" href="/collections/tasks" empty="Gecikmiş görev yok.">
          {agent.overdue_tasks.map((t) => (
            <li key={t.id} className="flex justify-between gap-2 text-sm">
              <Link href={`/customers/${t.customer_id}`} className="truncate font-medium hover:text-primary">
                {t.customer_name}
              </Link>
              <span className="shrink-0 text-danger">{t.due_date}</span>
            </li>
          ))}
        </Panel>
      ) : null}
      {show.promises ? (
        <Panel title="Bugünkü ödeme sözleri" href="/promises" empty="Bugün söz yok.">
          {agent.promises_today.map((p) => (
            <li key={p.id} className="flex justify-between gap-2 text-sm">
              <Link href={`/customers/${p.customer_id}`} className="truncate font-medium hover:text-primary">
                {p.customer_name}
              </Link>
              <span className="shrink-0 text-muted">{formatMoney(p.amount, currency)}</span>
            </li>
          ))}
        </Panel>
      ) : null}
      {show.activities ? (
        <Panel title="Son aktiviteler" href="/collections" empty="Henüz aktivite yok.">
          {agent.recent_activities.map((a) => (
            <li key={a.id} className="text-sm">
              <Link href={`/customers/${a.customer_id}`} className="font-medium hover:text-primary">
                {a.customer_name}
              </Link>
              <p className="text-xs text-muted">
                {a.summary} · {formatDate(a.occurred_at.slice(0, 10))}
              </p>
            </li>
          ))}
        </Panel>
      ) : null}
    </div>
  );
}

function Panel({
  title,
  href,
  empty,
  children,
}: {
  title: string;
  href: string;
  empty: string;
  children: ReactNode;
}) {
  const count = Array.isArray(children) ? children.length : children ? 1 : 0;
  return (
    <section className="rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <Link href={href} className="text-xs font-medium text-primary hover:underline">
          Tümü
        </Link>
      </div>
      {count > 0 ? <ul className="space-y-2">{children}</ul> : <p className="text-sm text-muted">{empty}</p>}
    </section>
  );
}
