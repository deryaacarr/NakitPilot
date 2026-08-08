"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { TASK_TYPE_LABELS, type CollectionTask } from "@/lib/collections/types";
import { cn } from "@/lib/cn";
import { formatDate, formatMoney } from "@/lib/customers/format";
import { RISK_LABELS, type RiskStatus } from "@/lib/customers/types";
import type { SemanticTone } from "@/lib/design/semantic";

function riskTone(status: string): SemanticTone {
  if (status === "LOW") return "success";
  if (status === "MEDIUM") return "warning";
  if (status === "HIGH" || status === "CRITICAL") return "danger";
  return "neutral";
}

function priorityTone(priority: string): SemanticTone {
  if (priority === "CRITICAL" || priority === "HIGH") return "danger";
  if (priority === "MEDIUM") return "warning";
  return "neutral";
}

export type TaskCardActions = {
  onStart?: () => void;
  onComplete?: () => void;
  onPostpone?: () => void;
  onAssign?: () => void;
  onPrepare?: () => void;
};

export function TaskCard({
  task,
  actions,
  compact,
  className,
}: {
  task: CollectionTask;
  actions?: TaskCardActions;
  compact?: boolean;
  className?: string;
}) {
  const closed = task.status === "COMPLETED" || task.status === "CANCELLED";
  const openBalance = task.open_balance ?? task.overdue_balance;
  const risk = task.customer_risk_status as RiskStatus;

  return (
    <article
      className={cn(
        "rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3",
        task.status === "IN_PROGRESS" && "border-brand/40 ring-1 ring-brand/20",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link
            href={`/customers/${task.customer}`}
            className="font-semibold text-foreground hover:underline"
          >
            {task.customer_name}
          </Link>
          <p className="mt-0.5 text-xs text-muted">
            {TASK_TYPE_LABELS[task.task_type] ?? task.task_type}
            {task.title ? ` · ${task.title}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatusChip tone={priorityTone(task.priority)} label={task.priority} />
          <StatusChip
            tone={riskTone(task.customer_risk_status)}
            label={RISK_LABELS[risk] ?? task.customer_risk_status}
          />
        </div>
      </div>

      <dl
        className={cn(
          "mt-3 grid gap-2 text-xs text-muted",
          compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4",
        )}
      >
        <Metric label="Açık bakiye" value={formatMoney(openBalance)} emphasize />
        <Metric
          label="Gecikme"
          value={task.overdue_days != null ? `${task.overdue_days} gün` : "—"}
        />
        <Metric
          label="Son iletişim"
          value={
            task.last_contact_at ? formatDate(task.last_contact_at.slice(0, 10)) : "—"
          }
        />
        <Metric
          label="Sorumlu"
          value={task.assigned_to_name || task.assigned_to_email || "—"}
        />
        <div className={compact ? "col-span-2" : "col-span-2 sm:col-span-4"}>
          <dt className="text-subtle">Ödeme sözü</dt>
          <dd className="font-medium text-foreground">
            {task.payment_promise
              ? `${formatMoney(task.payment_promise.amount)} · ${formatDate(task.payment_promise.promised_date)} (${task.payment_promise.status})`
              : "—"}
          </dd>
        </div>
      </dl>

      {!closed && actions ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {actions.onStart && task.status === "OPEN" ? (
            <Button type="button" size="sm" variant="outline" onClick={actions.onStart}>
              Başlat
            </Button>
          ) : null}
          {actions.onPrepare ? (
            <Button type="button" size="sm" variant="outline" onClick={actions.onPrepare}>
              Hazırla
            </Button>
          ) : null}
          {actions.onComplete ? (
            <Button type="button" size="sm" onClick={actions.onComplete}>
              Tamamla
            </Button>
          ) : null}
          {actions.onPostpone ? (
            <Button type="button" size="sm" variant="outline" onClick={actions.onPostpone}>
              Ertele
            </Button>
          ) : null}
          {actions.onAssign ? (
            <Button type="button" size="sm" variant="outline" onClick={actions.onAssign}>
              Başkasına ata
            </Button>
          ) : null}
          <Link
            href={`/customers/${task.customer}`}
            className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-border-default px-2.5 text-xs font-semibold"
          >
            Müşteriyi aç
          </Link>
        </div>
      ) : null}
    </article>
  );
}

function Metric({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div>
      <dt className="text-subtle">{label}</dt>
      <dd className={cn("font-medium text-foreground", emphasize && "tabular-nums")}>{value}</dd>
    </div>
  );
}
