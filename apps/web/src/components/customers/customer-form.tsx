"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { z } from "zod";

import {
  AppForm,
  AutosaveIndicator,
  FormRootError,
  FormSectionPanel,
  FormSectionTabs,
  SubmitButton,
} from "@/components/forms";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/datepicker";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { createCustomer, updateCustomer } from "@/lib/customers/api";
import { RISK_LABELS, type Customer, type RiskStatus } from "@/lib/customers/types";
import { applyBackendFieldErrors, useAppForm } from "@/lib/forms";
import { useAutosave } from "@/lib/forms/use-autosave";

const customerSchema = z.object({
  code: z.string(),
  name: z.string().min(1, "Müşteri adı gerekli"),
  tax_number: z.string(),
  email: z.union([z.literal(""), z.email("Geçerli bir e-posta girin")]),
  phone: z.string(),
  city: z.string(),
  sector: z.string(),
  payment_term_days: z.coerce.number().int().min(0, "Vade günü negatif olamaz"),
  credit_limit: z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0), {
    message: "Kredi limiti negatif olamaz",
  }),
  risk_status: z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
  risk_score: z.coerce.number().int().min(0).max(100),
  assigned_user: z.string(),
  collection_strategy: z.string(),
  notes: z.string(),
  is_active: z.boolean(),
});

type FormValues = z.infer<typeof customerSchema>;

type TabId = "general" | "contact" | "finance" | "collection" | "notes";

const TABS: { id: TabId; label: string }[] = [
  { id: "general", label: "Genel Bilgiler" },
  { id: "contact", label: "İletişim" },
  { id: "finance", label: "Finansal Ayarlar" },
  { id: "collection", label: "Tahsilat Ayarları" },
  { id: "notes", label: "Notlar" },
];

type MembershipRow = { user_id: number; user_email: string; organization: number };

export type CustomerFormProps = {
  mode: "create" | "edit";
  customer?: Customer;
  contactsSlot?: React.ReactNode;
};

export function CustomerForm({ mode, customer, contactsSlot }: CustomerFormProps) {
  const router = useRouter();
  const { toast } = useToast();
  const [tab, setTab] = useState<TabId>("general");
  const [assignees, setAssignees] = useState<MembershipRow[]>([]);

  const form = useAppForm({
    schema: customerSchema,
    defaultValues: {
      code: customer?.code ?? "",
      name: customer?.name ?? "",
      tax_number: customer?.tax_number ?? "",
      email: customer?.email ?? "",
      phone: customer?.phone ?? "",
      city: customer?.city ?? "",
      sector: customer?.sector ?? "",
      payment_term_days: customer?.payment_term_days ?? 30,
      credit_limit: customer?.credit_limit ?? "0.00",
      risk_status: (customer?.risk_status ?? "LOW") as RiskStatus,
      risk_score: customer?.risk_score ?? 0,
      assigned_user: customer?.assigned_user != null ? String(customer.assigned_user) : "",
      collection_strategy: customer?.collection_strategy ?? "",
      notes: customer?.notes ?? "",
      is_active: customer?.is_active ?? true,
    },
  });

  const notesValue = form.watch("notes");
  const autosave = useAutosave({
    value: notesValue,
    enabled: mode === "edit" && Boolean(customer?.id) && tab === "notes",
    debounceMs: 900,
    serialize: (v) => v,
    save: async (notes) => {
      const result = await updateCustomer(customer!.id, { notes });
      if (!result.ok) return { ok: false, message: result.error.message };
    },
  });

  useEffect(() => {
    void (async () => {
      const memberships = await apiRequest<MembershipRow[]>("/api/memberships/me/");
      if (!memberships.ok || memberships.data.length === 0) return;
      const orgId = memberships.data[0].organization;
      const orgMembers = await apiRequest<MembershipRow[]>(
        `/api/organizations/${orgId}/memberships/`,
      );
      if (orgMembers.ok) {
        const list = Array.isArray(orgMembers.data)
          ? orgMembers.data
          : ((orgMembers.data as { results?: MembershipRow[] }).results ?? []);
        setAssignees(list);
      }
    })();
  }, []);

  const onSubmit = async (values: FormValues) => {
    const payload = {
      code: values.code,
      name: values.name,
      tax_number: values.tax_number,
      email: values.email,
      phone: values.phone,
      city: values.city,
      sector: values.sector,
      payment_term_days: values.payment_term_days,
      credit_limit: values.credit_limit || "0.00",
      risk_status: values.risk_status,
      risk_score: values.risk_score,
      assigned_user: values.assigned_user ? Number(values.assigned_user) : null,
      collection_strategy: values.collection_strategy,
      notes: values.notes,
      is_active: values.is_active,
    };

    const result =
      mode === "create"
        ? await createCustomer(payload)
        : await updateCustomer(customer!.id, payload);

    if (!result.ok) {
      applyBackendFieldErrors(form.setError, result.error);
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }

    form.reset(values);
    toast({
      title: mode === "create" ? "Müşteri oluşturuldu" : "Müşteri güncellendi",
      tone: "success",
    });
    router.push(`/customers/${result.data.id}`);
    router.refresh();
  };

  const {
    register,
    formState: { errors, isSubmitting },
  } = form;

  const errorSections: Partial<Record<TabId, boolean>> = {
    general: Boolean(errors.code || errors.name || errors.tax_number || errors.sector),
    contact: Boolean(errors.email || errors.phone || errors.city),
    finance: Boolean(
      errors.payment_term_days || errors.credit_limit || errors.risk_status || errors.risk_score,
    ),
    collection: Boolean(errors.assigned_user || errors.collection_strategy),
    notes: Boolean(errors.notes),
  };

  return (
    <div className="space-y-4">
      <FormSectionTabs
        sections={TABS}
        active={tab}
        onChange={setTab}
        errorSections={errorSections}
      />

      {tab === "contact" && mode === "edit" && contactsSlot ? (
        <div className="space-y-4">
          <FormSectionPanel title="İletişim bilgileri">
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="E-posta"
                type="email"
                error={errors.email?.message}
                {...register("email")}
              />
              <Input label="Telefon" error={errors.phone?.message} {...register("phone")} />
              <Input label="Şehir" error={errors.city?.message} {...register("city")} />
            </div>
          </FormSectionPanel>
          <FormSectionPanel title="İletişim kişileri">{contactsSlot}</FormSectionPanel>
          <AppForm form={form} onSubmit={onSubmit} className="flex gap-2">
            <FormRootError />
            <SubmitButton>Kaydet</SubmitButton>
          </AppForm>
        </div>
      ) : (
        <AppForm form={form} onSubmit={onSubmit} className="space-y-4">
          <FormRootError />

          {tab === "general" ? (
            <FormSectionPanel title="Genel bilgiler">
              <div className="grid gap-4 md:grid-cols-2">
                <Input label="Müşteri kodu" error={errors.code?.message} {...register("code")} />
                <Input label="Müşteri adı" error={errors.name?.message} {...register("name")} />
                <Input
                  label="Vergi / TCKN"
                  error={errors.tax_number?.message}
                  {...register("tax_number")}
                />
                <Input label="Sektör" error={errors.sector?.message} {...register("sector")} />
                <label className="flex items-center gap-2 text-sm text-foreground md:col-span-2">
                  <input
                    type="checkbox"
                    className="size-4 rounded border-border-default"
                    {...register("is_active")}
                  />
                  Aktif müşteri
                </label>
              </div>
            </FormSectionPanel>
          ) : null}

          {tab === "contact" ? (
            <FormSectionPanel title="İletişim">
              {mode === "create" ? (
                <p className="mb-3 text-sm text-muted">
                  İletişim kişileri müşteri kaydedildikten sonra eklenebilir.
                </p>
              ) : null}
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="E-posta"
                  type="email"
                  error={errors.email?.message}
                  {...register("email")}
                />
                <Input label="Telefon" error={errors.phone?.message} {...register("phone")} />
                <Input label="Şehir" error={errors.city?.message} {...register("city")} />
              </div>
            </FormSectionPanel>
          ) : null}

          {tab === "finance" ? (
            <FormSectionPanel title="Finansal ayarlar">
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Vade günü"
                  type="number"
                  min={0}
                  error={errors.payment_term_days?.message}
                  {...register("payment_term_days")}
                />
                <Input
                  label="Kredi limiti (TRY)"
                  error={errors.credit_limit?.message}
                  {...register("credit_limit")}
                />
                <Select
                  label="Risk seviyesi"
                  options={(Object.keys(RISK_LABELS) as RiskStatus[]).map((value) => ({
                    value,
                    label: RISK_LABELS[value],
                  }))}
                  error={errors.risk_status?.message}
                  {...register("risk_status")}
                />
                <Input
                  label="Risk skoru (0–100)"
                  type="number"
                  min={0}
                  max={100}
                  error={errors.risk_score?.message}
                  {...register("risk_score")}
                />
                {mode === "edit" && customer?.last_contact_at ? (
                  <DatePicker
                    label="Son iletişim (salt okunur)"
                    value={customer.last_contact_at.slice(0, 10)}
                    disabled
                  />
                ) : null}
              </div>
            </FormSectionPanel>
          ) : null}

          {tab === "collection" ? (
            <FormSectionPanel
              title="Tahsilat ayarları"
              description="Sorumlu kullanıcı ve tahsilat stratejisi."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Select
                  label="Sorumlu kullanıcı"
                  options={assignees.map((m) => ({
                    value: String(m.user_id),
                    label: m.user_email,
                  }))}
                  placeholder="Seçiniz"
                  error={errors.assigned_user?.message}
                  {...register("assigned_user")}
                />
                <Input
                  label="Tahsilat stratejisi"
                  placeholder="Örn: Haftalık arama, e-posta öncelikli"
                  error={errors.collection_strategy?.message}
                  {...register("collection_strategy")}
                />
              </div>
              {mode === "edit" && customer ? (
                <p className="mt-3 text-xs text-muted">
                  İletişim kanal tercihleri için{" "}
                  <Link
                    href={`/customers/${customer.id}`}
                    className={cn("font-semibold text-brand hover:underline")}
                  >
                    müşteri kartındaki iletişim paneli
                  </Link>
                  ne bakın.
                </p>
              ) : null}
            </FormSectionPanel>
          ) : null}

          {tab === "notes" ? (
            <FormSectionPanel title="Notlar">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-xs text-muted">
                  {mode === "edit" ? "Değişiklikler otomatik kaydedilir." : "Kayıt ile birlikte saklanır."}
                </p>
                <AutosaveIndicator status={autosave.status} errorMessage={autosave.errorMessage} />
              </div>
              <Textarea
                label="Notlar"
                rows={8}
                error={errors.notes?.message}
                {...register("notes")}
              />
            </FormSectionPanel>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <SubmitButton>{mode === "create" ? "Oluştur" : "Kaydet"}</SubmitButton>
            <Button
              type="button"
              variant="outline"
              disabled={isSubmitting}
              onClick={() => router.back()}
            >
              Vazgeç
            </Button>
          </div>
        </AppForm>
      )}
    </div>
  );
}
