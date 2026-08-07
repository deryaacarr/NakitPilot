"use client";

import { useCallback, useEffect, useState } from "react";
import { z } from "zod";

import { ErrorState } from "@/components/errors";
import { AppForm, SubmitButton } from "@/components/forms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingSkeleton } from "@/components/ui/loading-skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { createContact, deleteContact, listContacts, updateContact } from "@/lib/customers/api";
import { copyToClipboard } from "@/lib/customers/format";
import type { CustomerContact } from "@/lib/customers/types";
import type { AppError } from "@/lib/errors";
import { applyBackendFieldErrors, useAppForm } from "@/lib/forms";

const contactSchema = z.object({
  full_name: z.string().min(1, "Ad gerekli"),
  title: z.string(),
  email: z.union([z.literal(""), z.email("Geçerli e-posta girin")]),
  phone: z.string(),
  is_primary: z.boolean(),
  notes: z.string(),
});

type ContactFormValues = z.infer<typeof contactSchema>;

export function CustomerContactsPanel({ customerId }: { customerId: number }) {
  const { toast } = useToast();
  const [contacts, setContacts] = useState<CustomerContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<AppError | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  const form = useAppForm({
    schema: contactSchema,
    defaultValues: {
      full_name: "",
      title: "",
      email: "",
      phone: "",
      is_primary: false,
      notes: "",
    },
    warnUnsavedChanges: false,
  });

  const load = useCallback(async () => {
    const result = await listContacts(customerId);
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    setContacts(result.data);
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await listContacts(customerId);
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setError(null);
      setContacts(result.data);
    });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  const resetForm = () => {
    setEditingId(null);
    form.reset({
      full_name: "",
      title: "",
      email: "",
      phone: "",
      is_primary: false,
      notes: "",
    });
  };

  const onSubmit = async (values: ContactFormValues) => {
    const result =
      editingId == null
        ? await createContact(customerId, values)
        : await updateContact(customerId, editingId, values);

    if (!result.ok) {
      applyBackendFieldErrors(form.setError, result.error);
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }

    toast({
      title: editingId == null ? "Kişi eklendi" : "Kişi güncellendi",
      tone: "success",
    });
    resetForm();
    setLoading(true);
    await load();
  };

  const startEdit = (contact: CustomerContact) => {
    setEditingId(contact.id);
    form.reset({
      full_name: contact.full_name,
      title: contact.title,
      email: contact.email,
      phone: contact.phone,
      is_primary: contact.is_primary,
      notes: contact.notes,
    });
  };

  const onDelete = async (contactId: number) => {
    const result = await deleteContact(customerId, contactId);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    toast({ title: "Kişi silindi", tone: "success" });
    if (editingId === contactId) resetForm();
    setLoading(true);
    await load();
  };

  const copy = async (label: string, value: string) => {
    if (!value) return;
    const ok = await copyToClipboard(value);
    toast({
      title: ok ? `${label} kopyalandı` : "Kopyalanamadı",
      tone: ok ? "success" : "error",
    });
  };

  const {
    register,
    formState: { errors },
  } = form;

  if (loading) return <LoadingSkeleton lines={4} />;
  if (error) return <ErrorState error={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        {contacts.length === 0 ? (
          <EmptyState
            title="İletişim kişisi yok"
            description="Bu müşteri için henüz kişi eklenmemiş."
          />
        ) : (
          contacts.map((contact) => (
            <div
              key={contact.id}
              className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-4 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold text-slate-900">{contact.full_name}</p>
                  {contact.is_primary ? <Badge tone="brand">Ana iletişim</Badge> : null}
                </div>
                {contact.title ? <p className="text-sm text-slate-500">{contact.title}</p> : null}
                <div className="flex flex-wrap gap-2 pt-1">
                  {contact.phone ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void copy("Telefon", contact.phone)}
                    >
                      Tel: {contact.phone}
                    </Button>
                  ) : null}
                  {contact.email ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void copy("E-posta", contact.email)}
                    >
                      {contact.email}
                    </Button>
                  ) : null}
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="ghost" onClick={() => startEdit(contact)}>
                  Düzenle
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="danger"
                  onClick={() => void onDelete(contact.id)}
                >
                  Sil
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-900">
          {editingId == null ? "Yeni kişi ekle" : "Kişiyi düzenle"}
        </h3>
        <AppForm form={form} onSubmit={onSubmit} className="grid gap-3 md:grid-cols-2">
          <Input label="Ad soyad" error={errors.full_name?.message} {...register("full_name")} />
          <Input label="Ünvan" error={errors.title?.message} {...register("title")} />
          <Input
            label="E-posta"
            type="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <Input label="Telefon" error={errors.phone?.message} {...register("phone")} />
          <div className="md:col-span-2">
            <Textarea label="Not" rows={3} error={errors.notes?.message} {...register("notes")} />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
            <input
              type="checkbox"
              className="size-4 rounded border-slate-300"
              {...register("is_primary")}
            />
            Ana iletişim kişisi
          </label>
          <div className="flex gap-2 md:col-span-2">
            <SubmitButton>{editingId == null ? "Ekle" : "Güncelle"}</SubmitButton>
            {editingId != null ? (
              <Button type="button" variant="outline" onClick={resetForm}>
                İptal
              </Button>
            ) : null}
          </div>
        </AppForm>
      </div>
    </div>
  );
}
