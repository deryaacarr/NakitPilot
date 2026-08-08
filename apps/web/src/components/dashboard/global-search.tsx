"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { globalSearch, type GlobalSearchResult, type SearchHit } from "@/lib/search/api";

const RECENT_KEY = "nakitpilot.search_recent";
const GROUPS: { key: "customers" | "invoices" | "tasks" | "payments"; label: string }[] = [
  { key: "customers", label: "Müşteriler" },
  { key: "invoices", label: "Faturalar" },
  { key: "tasks", label: "Görevler" },
  { key: "payments", label: "Ödemeler" },
];

function loadRecent(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    const parsed = raw ? (JSON.parse(raw) as string[]) : [];
    return Array.isArray(parsed) ? parsed.slice(0, 6) : [];
  } catch {
    return [];
  }
}

function saveRecent(q: string) {
  const next = [q, ...loadRecent().filter((x) => x !== q)].slice(0, 6);
  window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GlobalSearchResult | null>(null);
  const [recent, setRecent] = useState<string[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const timerRef = useRef<number | null>(null);

  const grouped = useMemo(() => {
    if (!result) {
      return { customers: [], invoices: [], tasks: [], payments: [] } as Record<
        (typeof GROUPS)[number]["key"],
        SearchHit[]
      >;
    }
    return {
      customers: result.customers || [],
      invoices: result.invoices || [],
      tasks: result.tasks || [],
      // Acceptance: 4 groups — promises fold into Ödemeler
      payments: [...(result.payments || []), ...(result.promises || [])],
    };
  }, [result]);

  const flatHits = useMemo(() => GROUPS.flatMap((g) => grouped[g.key]), [grouped]);

  const runSearch = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResult(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const started = performance.now();
    const res = await globalSearch(q.trim());
    setLoading(false);
    if (res.ok) {
      setResult(res.data);
      setActiveIndex(0);
      // Soft client-side latency note (acceptance <300ms network-dependent)
      if (performance.now() - started > 300) {
        // keep silent; still show results
      }
    }
  }, []);

  useEffect(() => {
    setRecent(loadRecent());
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      }
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      void runSearch(query);
    }, 180);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [query, runSearch]);

  function selectHit(hit: SearchHit) {
    saveRecent(query.trim() || hit.label);
    setRecent(loadRecent());
    setOpen(false);
    window.location.href = hit.href;
  }

  return (
    <div className="relative min-w-0 flex-1 max-w-md">
      <button
        type="button"
        className="flex h-9 w-full items-center gap-2 rounded-[var(--radius-md)] border border-border-default bg-surface-secondary px-3 text-left text-sm text-muted hover:border-border-strong"
        onClick={() => {
          setOpen(true);
          window.setTimeout(() => inputRef.current?.focus(), 0);
        }}
      >
        <span aria-hidden>⌕</span>
        <span className="truncate">Müşteri, fatura, vergi no, görev…</span>
        <kbd className="ml-auto hidden rounded border border-border-default px-1.5 text-[10px] sm:inline">
          ⌘K
        </kbd>
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-surface-inverse/40 p-4 pt-[12vh]"
          onClick={() => setOpen(false)}
        >
          <div
            id={panelId}
            role="dialog"
            aria-label="Global arama"
            className="w-full max-w-xl overflow-hidden rounded-[var(--radius-lg)] border border-border-default bg-surface-primary shadow-[var(--shadow-lg)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b border-border-default p-3">
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Müşteri, fatura no, vergi no, telefon, görev, söz…"
                className="h-11 w-full rounded-[var(--radius-md)] border border-border-default bg-surface-secondary px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActiveIndex((i) => Math.min(i + 1, Math.max(flatHits.length - 1, 0)));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActiveIndex((i) => Math.max(i - 1, 0));
                  } else if (e.key === "Enter" && flatHits[activeIndex]) {
                    e.preventDefault();
                    selectHit(flatHits[activeIndex]);
                  }
                }}
              />
            </div>
            <div className="max-h-[24rem] overflow-y-auto p-2">
              {query.trim().length < 2 ? (
                <div className="p-2">
                  <p className="px-2 text-xs font-semibold uppercase tracking-[0.12em] text-subtle">
                    Son aramalar
                  </p>
                  {recent.length === 0 ? (
                    <p className="px-2 py-3 text-sm text-muted">Henüz arama yok. En az 2 karakter yazın.</p>
                  ) : (
                    <ul>
                      {recent.map((item) => (
                        <li key={item}>
                          <button
                            type="button"
                            className="w-full rounded-[var(--radius-md)] px-3 py-2 text-left text-sm hover:bg-surface-tertiary"
                            onClick={() => setQuery(item)}
                          >
                            {item}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : loading ? (
                <p className="p-3 text-sm text-muted">Aranıyor…</p>
              ) : flatHits.length === 0 ? (
                <p className="p-3 text-sm text-muted">Sonuç bulunamadı.</p>
              ) : (
                GROUPS.map((group) => {
                  const rows = grouped[group.key];
                  if (!rows.length) return null;
                  return (
                    <div key={group.key} className="mb-2">
                      <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle">
                        {group.label}
                      </p>
                      <ul>
                        {rows.map((hit) => {
                          const idx = flatHits.findIndex(
                            (h) => h.href === hit.href && h.id === hit.id,
                          );
                          const active = idx === activeIndex;
                          return (
                            <li key={`${group.key}-${hit.id}`}>
                              <Link
                                href={hit.href}
                                className={[
                                  "block rounded-[var(--radius-md)] px-3 py-2",
                                  active ? "bg-primary/10 text-primary" : "hover:bg-surface-tertiary",
                                ].join(" ")}
                                onClick={() => {
                                  saveRecent(query.trim());
                                  setOpen(false);
                                }}
                                onMouseEnter={() => setActiveIndex(idx)}
                              >
                                <p className="text-sm font-medium">{hit.label}</p>
                                {hit.subtitle ? (
                                  <p className="text-xs text-muted">{hit.subtitle}</p>
                                ) : null}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
