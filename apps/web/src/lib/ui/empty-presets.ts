/**
 * NP-470 — page-level empty state copy (what / why / primary action).
 */
export type EmptyPreset = {
  title: string;
  description: string;
  why?: string;
  actionLabel: string;
  actionHref?: string;
};

export const EMPTY_PRESETS = {
  promises: {
    title: "Henüz ödeme sözü bulunmuyor.",
    description:
      "Müşterilerden aldığınız ödeme sözlerini kaydederek tahsilat takibini daha doğru yapabilirsiniz.",
    why: "Söz tarihleri gecikme ve nakit planını erken gösterir.",
    actionLabel: "Ödeme Sözü Ekle",
    actionHref: "/promises?create=1",
  },
  customers: {
    title: "Henüz müşteri kaydı yok.",
    description: "Müşteri ekleyerek fatura, ödeme ve tahsilat takibine başlayın.",
    why: "Tüm tahsilat akışı müşteri kartı üzerinden yürür.",
    actionLabel: "Müşteri Ekle",
    actionHref: "/customers/new",
  },
  invoices: {
    title: "Henüz fatura bulunmuyor.",
    description: "Açık faturaları kaydederek gecikme ve nakit akışını izleyin.",
    why: "Forecast ve tahsilat önceliği faturalara dayanır.",
    actionLabel: "Fatura Ekle",
    actionHref: "/invoices/new",
  },
  payments: {
    title: "Henüz ödeme kaydı yok.",
    description: "Gelen ödemeleri işleyerek açık bakiyeyi güncel tutun.",
    why: "Ödeme kayıtları söz ve risk durumunu otomatik günceller.",
    actionLabel: "Ödeme Gir",
    actionHref: "/payments/new",
  },
  tasks: {
    title: "Bugün için açık görev yok.",
    description: "Gecikmiş veya yaklaşan tahsilat görevleri burada görünür.",
    why: "Günlük çalışma listesi tahsilat hızını artırır.",
    actionLabel: "Görev Oluştur",
    actionHref: "/collections/tasks?create=1",
  },
  notifications: {
    title: "Bildirim yok.",
    description: "Kritik söz bozulmaları ve görev hatırlatmaları burada listelenir.",
    why: "Aksiyon gerektiren olayları kaçırmamanızı sağlar.",
    actionLabel: "Görevlere Git",
    actionHref: "/collections",
  },
  timeline: {
    title: "Aktivite yok.",
    description: "Arama, ödeme, söz ve notlar zaman çizelgesinde birikir.",
    why: "Müşteri geçmişi görüşme hazırlığını hızlandırır.",
    actionLabel: "Not Ekle",
  },
} as const satisfies Record<string, EmptyPreset>;
