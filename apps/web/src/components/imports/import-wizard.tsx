"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  commitImport,
  downloadImportErrors,
  downloadInvoiceTemplate,
  getImportJob,
  previewImport,
  saveImportMapping,
  uploadInvoiceImport,
} from "@/lib/imports/api";
import type {
  CanonicalField,
  DuplicatePolicy,
  ImportPreviewError,
  ImportPreviewSummary,
  ImportJob,
} from "@/lib/imports/types";
import { cn } from "@/lib/cn";

type Step = "upload" | "mapping" | "preview" | "results";

const DUPLICATE_OPTIONS = [
  { value: "SKIP", label: "Satırı atla (önerilen)" },
  { value: "UPDATE", label: "Mevcut kaydı güncelle" },
  { value: "CREATE", label: "Yeni kayıt olarak ekle" },
];

export function ImportWizard() {
  const { toast } = useToast();
  const [step, setStep] = useState<Step>("upload");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [fields, setFields] = useState<CanonicalField[]>([]);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [duplicatePolicy, setDuplicatePolicy] = useState<DuplicatePolicy>("SKIP");
  const [summary, setSummary] = useState<ImportPreviewSummary | null>(null);
  const [errors, setErrors] = useState<ImportPreviewError[]>([]);
  const [polling, setPolling] = useState(false);

  const headerOptions = useMemo(() => {
    const headers = job?.headers ?? [];
    return [
      { value: "", label: "— Eşleme yok —" },
      ...headers.map((h) => ({ value: h, label: h })),
    ];
  }, [job]);

  useEffect(() => {
    if (!polling || !job?.id) return;
    const jobId = job.id;
    let cancelled = false;
    const tick = async () => {
      const result = await getImportJob(jobId);
      if (cancelled || !result.ok) return;
      setJob(result.data);
      if (result.data.status === "COMPLETED" || result.data.status === "FAILED") {
        setPolling(false);
        setBusy(false);
        setStep("results");
        if (result.data.status === "COMPLETED") {
          toast({ title: "İçe aktarma tamamlandı", tone: "success" });
        } else {
          toast({
            title: "İçe aktarma başarısız",
            description: result.data.error_message || undefined,
            tone: "error",
          });
        }
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [polling, job?.id, toast]);

  const onDownloadTemplate = async () => {
    const result = await downloadInvoiceTemplate();
    if (!result.ok) {
      toast({ title: "İndirme hatası", description: result.message, tone: "error" });
      return;
    }
    toast({ title: "Şablon indirildi", tone: "success" });
  };

  const onUpload = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    const result = await uploadInvoiceImport(file);
    setBusy(false);
    if (!result.ok) {
      toast({
        title: result.error.title,
        description: result.error.message,
        tone: "error",
      });
      return;
    }
    setJob(result.data.job);
    setFields(result.data.canonical_fields);
    setMapping(result.data.suggested_mapping);
    setSummary(null);
    setErrors([]);
    setStep("mapping");
    toast({
      title: "Dosya yüklendi",
      description: result.data.job.original_filename,
      tone: "success",
    });
  };

  const onSaveMapping = async () => {
    if (!job) return;
    setBusy(true);
    const result = await saveImportMapping(job.id, mapping);
    setBusy(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    if (result.data.unmapped_required.length > 0) {
      toast({
        title: "Eksik eşleme",
        description: `Zorunlu alanlar: ${result.data.unmapped_required.join(", ")}`,
        tone: "warning",
      });
      return;
    }
    setJob(result.data.job);
    setStep("preview");
    await runPreview(result.data.job.id);
  };

  const runPreview = async (jobId: number) => {
    setBusy(true);
    const result = await previewImport(jobId, {
      columnMapping: mapping,
      duplicatePolicy,
    });
    setBusy(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    setJob(result.data.job);
    setSummary(result.data.summary);
    setErrors(result.data.errors);
    setStep("preview");
  };

  const onCommit = async () => {
    if (!job) return;
    setBusy(true);
    const result = await commitImport(job.id, duplicatePolicy);
    if (!result.ok) {
      setBusy(false);
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    setJob(result.data.job);
    setPolling(true);
    toast({ title: "İşlem kuyruğa alındı", description: "Sonuç bekleniyor…" });
  };

  const onDownloadErrors = async () => {
    if (!job) return;
    const result = await downloadImportErrors(job.id);
    if (!result.ok) {
      toast({ title: "İndirme hatası", description: result.message, tone: "error" });
      return;
    }
    toast({ title: "Hata dosyası indirildi", tone: "success" });
  };

  const steps: Array<[Step, string]> = [
    ["upload", "1. Yükleme"],
    ["mapping", "2. Kolon eşleme"],
    ["preview", "3. Önizleme"],
    ["results", "4. Sonuç"],
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-slate-900">İçe aktarma</h1>
          <p className="mt-1 text-sm text-slate-600">
            Excel/CSV fatura yükleme — önce önizleme, sonra arka planda kayıt
          </p>
        </div>
        <Button type="button" variant="outline" onClick={() => void onDownloadTemplate()}>
          Örnek şablonu indir
        </Button>
      </div>

      <ol className="flex flex-wrap gap-2 text-sm">
        {steps.map(([id, label]) => (
          <li
            key={id}
            className={cn(
              "rounded-lg px-3 py-1.5 font-medium",
              step === id ? "bg-brand/10 text-brand" : "bg-slate-100 text-slate-500",
            )}
          >
            {label}
          </li>
        ))}
      </ol>

      {step === "upload" ? (
        <section className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm text-slate-600">
            .xlsx / .csv dosyası seçin (max 10 MB). Veri hemen yazılmaz.
          </p>
          <label className="bg-brand text-brand-foreground mt-4 inline-flex cursor-pointer items-center rounded-lg px-4 py-2.5 text-sm font-semibold hover:bg-teal-800">
            {busy ? "Yükleniyor…" : "Dosya seç"}
            <input
              type="file"
              accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              className="hidden"
              disabled={busy}
              onChange={(event) => void onUpload(event.target.files?.[0] ?? null)}
            />
          </label>
        </section>
      ) : null}

      {step === "mapping" && job ? (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-600">
            Dosya: <span className="font-medium text-slate-900">{job.original_filename}</span> ·{" "}
            {job.total_rows} satır
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {fields.map((field) => (
              <Select
                key={field.key}
                label={`${field.label}${field.required ? " *" : ""}`}
                options={headerOptions}
                value={mapping[field.key] ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  setMapping((current) => ({
                    ...current,
                    [field.key]: value || null,
                  }));
                }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" loading={busy} onClick={() => void onSaveMapping()}>
              Kaydet ve önizle
            </Button>
            <Button type="button" variant="outline" onClick={() => setStep("upload")}>
              Geri
            </Button>
          </div>
        </section>
      ) : null}

      {step === "preview" && summary ? (
        <section className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Stat label="Toplam satır" value={String(summary.total_rows)} />
            <Stat label="Geçerli satır" value={String(summary.valid_rows)} />
            <Stat label="Hatalı satır" value={String(summary.invalid_rows)} />
            <Stat label="Yeni müşteri" value={String(summary.new_customer_count)} />
            <Stat label="Yeni fatura" value={String(summary.new_invoice_count)} />
            <Stat label="Muhtemel tekrar" value={String(summary.likely_duplicate_count)} />
          </div>

          <div className="max-w-md">
            <Select
              label="Tekrarlayan fatura (NP-065)"
              options={DUPLICATE_OPTIONS}
              value={duplicatePolicy}
              onChange={(event) => setDuplicatePolicy(event.target.value as DuplicatePolicy)}
            />
            <p className="mt-1 text-xs text-slate-500">
              Varsayılan: satırı atla. Önizlemeyi yeniledikten sonra işleme alın.
            </p>
          </div>

          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            Önizleme veritabanına yazmaz. Kalıcı kayıt Celery kuyruğunda (commit) yapılır.
          </p>

          {errors.length > 0 ? (
            <ErrorTable errors={errors} />
          ) : (
            <p className="text-sm text-emerald-800">Önizlemede satır hatası yok.</p>
          )}

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setStep("mapping")}>
              Eşlemeye dön
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={busy}
              onClick={() => job && void runPreview(job.id)}
            >
              Önizlemeyi yenile
            </Button>
            <Button
              type="button"
              loading={busy || polling}
              disabled={!job || job.status !== "READY"}
              onClick={() => void onCommit()}
            >
              {polling ? "İşleniyor…" : "İçe aktarmayı başlat"}
            </Button>
          </div>
        </section>
      ) : null}

      {step === "results" && job ? (
        <section className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Durum" value={job.status} />
            <Stat label="Başarılı satırlar" value={String(job.successful_rows)} />
            <Stat label="Hatalı satırlar" value={String(job.failed_rows)} />
            <Stat label="Atlanan tekrarlar" value={String(job.skipped_duplicates)} />
          </div>

          {job.error_message ? (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-900">
              {job.error_message}
            </p>
          ) : null}

          {(job.preview_errors?.length ?? 0) > 0 ||
          job.failed_rows > 0 ||
          job.skipped_duplicates > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-900">Hata / atlama açıklamaları</h2>
                <Button type="button" variant="outline" onClick={() => void onDownloadErrors()}>
                  Hataları Excel olarak indir
                </Button>
              </div>
              <ErrorTable errors={(job.preview_errors ?? []) as ImportPreviewError[]} />
            </div>
          ) : (
            <p className="text-sm text-emerald-800">Tüm satırlar başarıyla işlendi.</p>
          )}

          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setStep("upload");
              setJob(null);
              setSummary(null);
              setErrors([]);
              setPolling(false);
            }}
          >
            Yeni içe aktarma
          </Button>
        </section>
      ) : null}
    </div>
  );
}

function ErrorTable({ errors }: { errors: ImportPreviewError[] }) {
  if (errors.length === 0) {
    return (
      <p className="text-sm text-slate-600">Detaylı satır hataları Excel indirmesinde yer alır.</p>
    );
  }
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold tracking-wide text-slate-500 uppercase">
          <tr>
            <th className="px-3 py-2">Satır</th>
            <th className="px-3 py-2">Alan</th>
            <th className="px-3 py-2">Değer</th>
            <th className="px-3 py-2">Hata</th>
          </tr>
        </thead>
        <tbody>
          {errors.slice(0, 50).map((err, index) => (
            <tr key={`${err.row_number}-${index}`} className="border-b border-slate-100">
              <td className="px-3 py-2">{err.row_number}</td>
              <td className="px-3 py-2">{err.field_name || "—"}</td>
              <td className="px-3 py-2">{err.raw_value || "—"}</td>
              <td className="px-3 py-2 text-red-700">{err.error_message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}
