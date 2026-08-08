"use client";

import { useState } from "react";

import { TaskCard } from "@/components/collections/task-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { StatusChip } from "@/components/ui/status-chip";
import { Surface } from "@/components/ui/surface";
import { Table } from "@/components/ui/table";
import type { CollectionTask } from "@/lib/collections/types";

const SAMPLE_TASK: CollectionTask = {
  id: 1,
  customer: 10,
  customer_name: "Demo Ticaret A.Ş.",
  customer_risk_status: "HIGH",
  customer_phone: "+905551112233",
  invoice: 100,
  invoice_number: "FTR-2026-001",
  task_type: "CALL",
  status: "OPEN",
  priority: "HIGH",
  priority_score: 90,
  title: "Gecikmiş fatura araması",
  description: "",
  due_date: "2026-08-08",
  assigned_to: 1,
  assigned_to_email: "finans@demo.example",
  assigned_to_name: "Ayşe Yılmaz",
  open_balance: "12500.00",
  overdue_balance: "12500.00",
  overdue_days: 18,
  last_contact_at: "2026-08-01T10:00:00Z",
  payment_promise: null,
};

const TABLE_ROWS = [
  { id: "1", customer: "Demo Ticaret", amount: "12.500 ₺", risk: "Yüksek" },
  { id: "2", customer: "Anadolu Lojistik", amount: "4.200 ₺", risk: "Orta" },
];

/**
 * NP-503 — stable fixtures for Playwright visual regression (no API).
 */
export function VisualGallery() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="space-y-8">
      <section data-testid="visual-button" className="space-y-3">
        <h2 className="np-section-title">Button</h2>
        <div className="flex flex-wrap gap-2">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
        </div>
      </section>

      <section data-testid="visual-input" className="max-w-sm space-y-3">
        <h2 className="np-section-title">Input</h2>
        <Input label="Müşteri adı" placeholder="Ara…" hint="Standart yükseklik" />
        <Input label="Hatalı alan" error="Bu alan zorunlu" defaultValue="" />
      </section>

      <section data-testid="visual-table" className="space-y-3">
        <h2 className="np-section-title">Table</h2>
        <Table
          rows={TABLE_ROWS}
          rowKey={(r) => r.id}
          columns={[
            { key: "customer", header: "Müşteri", cell: (r) => r.customer },
            { key: "amount", header: "Tutar", cell: (r) => r.amount },
            { key: "risk", header: "Risk", cell: (r) => r.risk },
          ]}
        />
      </section>

      <section data-testid="visual-modal" className="space-y-3">
        <h2 className="np-section-title">Modal</h2>
        <Button type="button" onClick={() => setModalOpen(true)}>
          Modal aç
        </Button>
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Görev tamamla"
          description="Örnek modal içeriği"
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setModalOpen(false)}>
                Vazgeç
              </Button>
              <Button onClick={() => setModalOpen(false)}>Kaydet</Button>
            </div>
          }
        >
          <p className="text-sm text-muted">Görsel regresyon için sabit içerik.</p>
        </Modal>
      </section>

      <section data-testid="visual-dashboard" className="space-y-3">
        <h2 className="np-section-title">Dashboard</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["Bugün tahsilat", "86.400 ₺"],
            ["Açık görev", "12"],
            ["Riskli müşteri", "5"],
          ].map(([label, value]) => (
            <Surface key={label} data-testid="visual-kpi">
              <p className="text-xs text-muted">{label}</p>
              <p className="np-metric mt-1">{value}</p>
            </Surface>
          ))}
        </div>
      </section>

      <section data-testid="visual-customer-detail" className="space-y-3">
        <h2 className="np-section-title">Customer detail</h2>
        <Surface>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-serif text-2xl text-foreground">Demo Ticaret A.Ş.</h3>
              <p className="text-sm text-muted">Kod: DEMO-01 · +90 555 111 22 33</p>
            </div>
            <StatusChip tone="danger" label="Yüksek" />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-subtle">Açık bakiye</dt>
              <dd className="font-semibold tabular-nums">12.500 ₺</dd>
            </div>
            <div>
              <dt className="text-subtle">Gecikme</dt>
              <dd className="font-semibold">18 gün</dd>
            </div>
            <div>
              <dt className="text-subtle">Sağlık</dt>
              <dd className="font-semibold">42</dd>
            </div>
            <div>
              <dt className="text-subtle">Söz</dt>
              <dd className="font-semibold">Yok</dd>
            </div>
          </dl>
        </Surface>
      </section>

      <section data-testid="visual-task-card" className="max-w-lg space-y-3">
        <h2 className="np-section-title">Task card</h2>
        <TaskCard
          task={SAMPLE_TASK}
          actions={{
            onComplete: () => undefined,
            onPrepare: () => undefined,
          }}
        />
      </section>

      <section data-testid="visual-risk-badge" className="space-y-3">
        <h2 className="np-section-title">Risk badge</h2>
        <div className="flex flex-wrap gap-2">
          <StatusChip tone="danger" label="Kritik" />
          <StatusChip tone="warning" label="Orta" />
          <StatusChip tone="success" label="Düşük" />
        </div>
      </section>
    </div>
  );
}
