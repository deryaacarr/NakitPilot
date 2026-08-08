"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Money } from "@/components/ui/money";
import { StatusChip } from "@/components/ui/status-chip";
import { FINANCIAL_COLOR_MEANING, type SemanticTone } from "@/lib/design/semantic";

const TONES = Object.keys(FINANCIAL_COLOR_MEANING) as SemanticTone[];

export function DesignSystemView() {
  return (
    <div className="space-y-[var(--space-8)]">
      <header className="space-y-[var(--space-2)]">
        <p className="np-helper uppercase tracking-[0.14em]">EPIC 37</p>
        <h1 className="np-page-title">Tasarım sistemi</h1>
        <p className="np-body text-muted max-w-2xl">
          Token kaynağı: <code className="text-primary">src/styles/tokens.css</code>. Renkler
          finansal anlam taşır; salt dekoratif kullanılmaz. Açık/koyu tema CSS değişkenleriyle
          yönetilir.
        </p>
      </header>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">Tipografi</h2>
        <div className="space-y-[var(--space-3)]">
          <p className="np-page-title">Page title 28–32</p>
          <p className="np-section-title">Section title 20–24</p>
          <p className="np-card-title">Card title 14–16</p>
          <p className="np-body">Body 14 — tahsilat ve nakit takip metni.</p>
          <p className="np-table-text">Table text 13 — satır verisi</p>
          <p className="np-metric">
            <Money value={128450.5} size="metric" />
          </p>
          <p className="np-helper">Helper text 12–13</p>
        </div>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">Finansal renk anlamları</h2>
        <ul className="grid gap-[var(--space-3)] sm:grid-cols-2 lg:grid-cols-3">
          {TONES.map((tone) => (
            <li key={tone} className="rounded-[var(--radius-md)] border border-border-default p-3">
              <StatusChip tone={tone} label={FINANCIAL_COLOR_MEANING[tone].label} />
              <p className="np-helper mt-2">
                {FINANCIAL_COLOR_MEANING[tone].color} · {tone}
              </p>
              <div className="mt-2 flex gap-2">
                <Badge tone={tone}>{tone}</Badge>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">UI kontrolleri</h2>
        <div className="flex flex-wrap gap-[var(--space-2)]">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
        </div>
        <div className="max-w-sm">
          <Input label="Standart input" placeholder="Yükseklik token" hint="--control-height-md" />
        </div>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">Spacing / radius / shadow</h2>
        <div className="flex flex-wrap items-end gap-[var(--space-3)]">
          {(["--space-1", "--space-2", "--space-3", "--space-4", "--space-6", "--space-8"] as const).map(
            (token) => (
              <div key={token} className="text-center">
                <div
                  className="bg-primary mx-auto rounded-[var(--radius-sm)]"
                  style={{ width: `var(${token})`, height: `var(${token})` }}
                />
                <p className="np-helper mt-1">{token}</p>
              </div>
            ),
          )}
        </div>
        <div className="grid gap-[var(--space-3)] sm:grid-cols-3">
          <div
            className="rounded-[var(--radius-sm)] border border-border-default bg-surface-secondary p-4"
            style={{ boxShadow: "var(--shadow-sm)" }}
          >
            radius-sm · shadow-sm
          </div>
          <div
            className="rounded-[var(--radius-md)] border border-border-default bg-surface-secondary p-4"
            style={{ boxShadow: "var(--shadow-md)" }}
          >
            radius-md · shadow-md
          </div>
          <div
            className="rounded-[var(--radius-lg)] border border-border-default bg-surface-secondary p-4"
            style={{ boxShadow: "var(--shadow-lg)" }}
          >
            radius-lg · shadow-lg
          </div>
        </div>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">Erişilebilirlik (EPIC 49)</h2>
        <ul className="np-body text-muted list-disc space-y-1 pl-5">
          <li>Normal metin kontrastı ≥ 4.5:1 · büyük metin ≥ 3:1 (açık ve koyu tema)</li>
          <li>Risk: renk + şekil (▲ kritik · ● orta · ✓ düşük)</li>
          <li>Dokunma hedefi: min. 44px (coarse pointer’da control-height)</li>
          <li>Modal/drawer: focus trap + Escape</li>
        </ul>
        <div className="flex flex-wrap gap-2">
          <StatusChip tone="danger" label="Kritik" />
          <StatusChip tone="warning" label="Orta" />
          <StatusChip tone="success" label="Düşük" />
        </div>
      </section>

      <section className="np-surface p-[var(--space-4)]">
        <h2 className="np-section-title mb-[var(--space-3)]">Para hizası (tabular)</h2>
        <table className="data-table w-full max-w-xs text-right">
          <tbody>
            {["1200.5", "98000", "15.25", "1250000.99"].map((v) => (
              <tr key={v} className="border-b border-border-default">
                <td className="py-2">
                  <Money value={v} size="table" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
