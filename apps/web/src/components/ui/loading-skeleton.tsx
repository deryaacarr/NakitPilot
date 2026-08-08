import { cn } from "@/lib/cn";

export type LoadingSkeletonProps = {
  className?: string;
  lines?: number;
};

/** Generic line skeleton (legacy). Prefer shaped variants below. */
export function LoadingSkeleton({ className, lines = 1 }: LoadingSkeletonProps) {
  return (
    <div
      className={cn("space-y-2", className)}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Yükleniyor"
    >
      <span className="sr-only">Yükleniyor…</span>
      <div aria-hidden className="space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <div
            key={index}
            className="h-4 animate-pulse rounded bg-surface-tertiary"
            style={{ width: `${100 - (index % 3) * 12}%` }}
          />
        ))}
      </div>
    </div>
  );
}

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-[var(--radius-md)] bg-surface-tertiary", className)}
      aria-hidden
    />
  );
}

/** NP-471 — content-shaped skeletons */
export function TableSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div
      className={cn(
        "space-y-2 rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4",
        className,
      )}
      role="status"
      aria-label="Tablo yükleniyor"
    >
      <span className="sr-only">Tablo yükleniyor…</span>
      <SkeletonBlock className="h-10 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonBlock key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function DashboardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)} role="status" aria-label="Dashboard yükleniyor">
      <span className="sr-only">Dashboard yükleniyor…</span>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBlock key={i} className="h-24" />
        ))}
      </div>
      <SkeletonBlock className="h-48 w-full" />
      <div className="grid gap-3 lg:grid-cols-2">
        <SkeletonBlock className="h-40" />
        <SkeletonBlock className="h-40" />
      </div>
    </div>
  );
}

export function DetailSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)} role="status" aria-label="Detay yükleniyor">
      <span className="sr-only">Detay yükleniyor…</span>
      <SkeletonBlock className="h-28 w-full" />
      <div className="grid gap-3 lg:grid-cols-3">
        <SkeletonBlock className="h-32 lg:col-span-2" />
        <SkeletonBlock className="h-32" />
      </div>
      <SkeletonBlock className="h-56 w-full" />
    </div>
  );
}

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-4",
        className,
      )}
      role="status"
      aria-label="Grafik yükleniyor"
    >
      <span className="sr-only">Grafik yükleniyor…</span>
      <SkeletonBlock className="mb-3 h-4 w-40" />
      <SkeletonBlock className="h-56 w-full" />
      <div className="mt-3 flex gap-2">
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-3 w-16" />
      </div>
    </div>
  );
}

export function TimelineSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)} role="status" aria-label="Zaman çizelgesi yükleniyor">
      <span className="sr-only">Zaman çizelgesi yükleniyor…</span>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <SkeletonBlock className="size-8 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <SkeletonBlock className="h-3 w-1/3" />
            <SkeletonBlock className="h-12 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DrawerSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)} role="status" aria-label="Panel yükleniyor">
      <span className="sr-only">Panel yükleniyor…</span>
      <SkeletonBlock className="h-6 w-1/2" />
      <SkeletonBlock className="h-20 w-full" />
      <SkeletonBlock className="h-20 w-full" />
      <SkeletonBlock className="h-10 w-full" />
    </div>
  );
}

export function TaskCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-lg)] border border-border-default bg-surface-primary p-3",
        className,
      )}
      aria-hidden
    >
      <SkeletonBlock className="h-5 w-2/3" />
      <div className="mt-3 grid grid-cols-2 gap-2">
        <SkeletonBlock className="h-8" />
        <SkeletonBlock className="h-8" />
      </div>
      <div className="mt-3 flex gap-2">
        <SkeletonBlock className="h-11 w-20" />
        <SkeletonBlock className="h-11 w-24" />
      </div>
    </div>
  );
}
