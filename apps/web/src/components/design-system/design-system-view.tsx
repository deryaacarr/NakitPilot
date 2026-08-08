"use client";

import { useState } from "react";

import {
  DashboardPage,
  DetailPage,
  FormPage,
  ListPage,
  ReportPage,
  SettingsPage,
  WizardPage,
} from "@/components/templates";
import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Money } from "@/components/ui/money";
import { Select } from "@/components/ui/select";
import { StatusChip } from "@/components/ui/status-chip";
import { Surface } from "@/components/ui/surface";
import { Textarea } from "@/components/ui/textarea";
import { FINANCIAL_COLOR_MEANING, type SemanticTone } from "@/lib/design/semantic";
import { AUDIT_SUMMARY_ROWS } from "@/lib/ui/component-audit";
import { BREAKPOINT_ACCEPTANCE, BREAKPOINTS } from "@/lib/ui/breakpoints";

import { VisualGallery } from "./visual-gallery";

const TONES = Object.keys(FINANCIAL_COLOR_MEANING) as SemanticTone[];

export function DesignSystemView() {
  const [settingsTab, setSettingsTab] = useState("profile");
  const [wizardStep, setWizardStep] = useState("upload");

  return (
    <div className="space-y-[var(--space-8)]">
      <header className="space-y-[var(--space-2)]">
        <p className="np-helper uppercase tracking-[0.14em]">EPIC 37 · 50</p>
        <h1 className="np-page-title">Tasarım sistemi</h1>
        <p className="np-body text-muted max-w-2xl">
          Token kaynağı: <code className="text-primary">src/styles/tokens.css</code>. Canonical
          bileşenler <code className="text-primary">components/ui</code>; sayfa şablonları{" "}
          <code className="text-primary">components/templates</code>.
        </p>
      </header>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]" data-testid="audit-summary">
        <h2 className="np-section-title">NP-500 — Component audit</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead className="text-xs tracking-wide text-subtle uppercase">
              <tr className="border-b border-border-default">
                <th className="py-2 pr-3">Kategori</th>
                <th className="py-2 pr-3">Sayım</th>
                <th className="py-2">Canonical</th>
              </tr>
            </thead>
            <tbody>
              {AUDIT_SUMMARY_ROWS.map((row) => (
                <tr key={row.category} className="border-b border-border-default">
                  <td className="py-2 pr-3 font-medium">{row.category}</td>
                  <td className="py-2 pr-3 text-muted">{row.count}</td>
                  <td className="py-2 text-muted">{row.canonical}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="np-helper">
          Birleştirme kuralı: ham CTA → Button/ButtonLink; slate kart → Surface; risk rengi →
          StatusChip.
        </p>
      </section>

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
          <ButtonLink href="/dashboard" variant="outline">
            ButtonLink
          </ButtonLink>
        </div>
        <div className="grid max-w-xl gap-3 sm:grid-cols-2">
          <Input label="Standart input" placeholder="Yükseklik token" hint="--control-height-md" />
          <Select
            label="Select"
            options={[
              { value: "a", label: "Seçenek A" },
              { value: "b", label: "Seçenek B" },
            ]}
          />
          <div className="sm:col-span-2">
            <Textarea label="Textarea" hint="Token border / focus" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Surface>
            <p className="np-card-title">Surface default</p>
            <p className="np-helper mt-1">np-surface</p>
          </Surface>
          <Surface tone="muted">
            <p className="np-card-title">Surface muted</p>
            <p className="np-helper mt-1">np-surface-muted</p>
          </Surface>
        </div>
      </section>

      <section className="space-y-[var(--space-3)]" data-testid="page-templates">
        <h2 className="np-section-title px-1">NP-501 — Sayfa şablonları</h2>
        <div className="grid gap-4 xl:grid-cols-2">
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Liste
            </div>
            <div className="scale-[0.92] origin-top p-3">
              <ListPage title="Müşteriler" description="Örnek liste" actions={<Button size="sm">Ekle</Button>}>
                <Surface tone="muted" padding="sm">
                  Tablo / kart alanı
                </Surface>
              </ListPage>
            </div>
          </Surface>
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Detay
            </div>
            <div className="scale-[0.92] origin-top p-3">
              <DetailPage title="Müşteri detay" aside={<Surface tone="muted" padding="sm">Özet</Surface>}>
                <Surface tone="muted" padding="sm">
                  İçerik
                </Surface>
              </DetailPage>
            </div>
          </Surface>
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Dashboard
            </div>
            <div className="scale-[0.92] origin-top p-3">
              <DashboardPage
                title="Ana sayfa"
                metrics={
                  <>
                    <Surface padding="sm">KPI</Surface>
                    <Surface padding="sm">KPI</Surface>
                  </>
                }
              >
                <Surface tone="muted" padding="sm">
                  Ana panel
                </Surface>
                <Surface tone="muted" padding="sm">
                  Yan panel
                </Surface>
              </DashboardPage>
            </div>
          </Surface>
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Ayar
            </div>
            <div className="scale-[0.92] origin-top p-3">
              <SettingsPage
                title="Ayarlar"
                nav={[
                  { id: "profile", label: "Profil" },
                  { id: "integrations", label: "Entegrasyon" },
                ]}
                activeId={settingsTab}
                onNavChange={setSettingsTab}
              >
                <p className="text-sm text-muted">Aktif: {settingsTab}</p>
              </SettingsPage>
            </div>
          </Surface>
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Wizard
            </div>
            <div className="scale-[0.92] origin-top p-3">
              <WizardPage
                title="İçe aktarma"
                steps={[
                  { id: "upload", label: "Yükle" },
                  { id: "map", label: "Eşle" },
                  { id: "done", label: "Bitir" },
                ]}
                activeStepId={wizardStep}
                footer={
                  <Button size="sm" onClick={() => setWizardStep("map")}>
                    İleri
                  </Button>
                }
              >
                <p className="text-sm text-muted">Adım içeriği</p>
              </WizardPage>
            </div>
          </Surface>
          <Surface className="overflow-hidden !p-0">
            <div className="border-b border-border-default px-3 py-2 text-xs font-semibold text-muted">
              Form · Rapor
            </div>
            <div className="space-y-4 scale-[0.92] origin-top p-3">
              <FormPage title="Yeni söz" footer={<Button size="sm">Kaydet</Button>}>
                <Input label="Tutar" />
              </FormPage>
              <ReportPage title="Yaşlandırma" filters={<Input label="Dönem" />} chart={<p>Grafik</p>}>
                <Surface tone="muted" padding="sm">
                  Rapor tablosu
                </Surface>
              </ReportPage>
            </div>
          </Surface>
        </div>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]" data-testid="breakpoint-audit">
        <h2 className="np-section-title">NP-502 — Responsive breakpoint’ler</h2>
        <ul className="flex flex-wrap gap-2">
          {Object.entries(BREAKPOINTS).map(([name, width]) => (
            <li
              key={name}
              className="rounded-[var(--radius-md)] border border-border-default px-3 py-1.5 text-xs font-semibold"
            >
              {name} · {width}px
            </li>
          ))}
        </ul>
        <ul className="np-body text-muted list-disc space-y-1 pl-5">
          {BREAKPOINT_ACCEPTANCE.map((item) => (
            <li key={item.width}>
              <strong className="text-foreground">{item.width}px:</strong> {item.rule}
            </li>
          ))}
        </ul>
        <p className="np-helper max-w-prose">
          Geniş ekranda satır ölçüsü: <code>max-w-prose</code> / PageShell{" "}
          <code>reading</code> · liste/dashboard <code>fluid</code> (max 90rem).
        </p>
      </section>

      <section className="np-surface p-[var(--space-4)] space-y-[var(--space-3)]">
        <h2 className="np-section-title">Erişilebilirlik</h2>
        <ul className="np-body text-muted list-disc space-y-1 pl-5">
          <li>Normal metin kontrastı ≥ 4.5:1 · büyük metin ≥ 3:1</li>
          <li>Risk: renk + şekil (▲ kritik · ● orta · ✓ düşük)</li>
          <li>Dokunma hedefi: min. 44px</li>
        </ul>
      </section>

      <section className="space-y-[var(--space-3)]">
        <h2 className="np-section-title">NP-503 — Visual gallery (aynı fixture: /ui-gallery)</h2>
        <VisualGallery />
      </section>
    </div>
  );
}
