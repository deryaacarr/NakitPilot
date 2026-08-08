"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

import {
  AppForm,
  FormRootError,
  FormSectionPanel,
  FormSectionTabs,
  PaymentFinancialHint,
  SubmitButton,
} from "@/components/forms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { applyBackendFieldErrors, useAppForm } from "@/lib/forms";
import { createPayment } from "@/lib/payments/api";

const paymentSchema = z.object({
  customer: z.string().min(1, "Müşteri seçin"),
  payment_date: z.string().min(1, "Tarih gerekli"),
  amount: z
    .string()
    .min(1, "Tutar gerekli")
    .refine((v) => !Number.isNaN(Number(v)) && Number(v) > 0, {
      message: "Tutar sıfırdan büyük olmalı",
    }),
  reference: z.string(),
  notes: z.string(),
});

type FormValues = z.infer<typeof paymentSchema>;
type SectionId = "customer" | "payment" | "notes";

const SECTIONS: { id: SectionId; label: string }[] = [
  { id: "customer", label: "Müşteri" },
  { id: "payment", label: "Ödeme" },
  { id: "notes", label: "Notlar" },
];

export function PaymentCreateForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [section, setSection] = useState<SectionId>("customer");

  const form = useAppForm({
    schema: paymentSchema,
    defaultValues: {
      customer: "",
      payment_date: new Date().toISOString().slice(0, 10),
      amount: "",
      reference: "",
      notes: "",
    },
  });

  useEffect(() => {
    void listCustomers({ page_size: 100 }).then((res) => {
      if (res.ok) setCustomers(res.data.results || []);
    });
  }, []);

  const {
    register,
    watch,
    formState: { errors, isSubmitting },
  } = form;

  const customerId = watch("customer");
  const amount = watch("amount");
  const selected = useMemo(
    () => customers.find((c) => String(c.id) === customerId) || null,
    [customers, customerId],
  );

  const onSubmit = async (values: FormValues) => {
    const res = await createPayment({
      customer: Number(values.customer),
      payment_date: values.payment_date,
      amount: values.amount,
      reference: values.reference,
      notes: values.notes,
      auto_allocate: true,
    });
    if (!res.ok) {
      applyBackendFieldErrors(form.setError, res.error);
      toast({ title: "Ödeme kaydedilemedi", description: res.error.message, tone: "error" });
      return;
    }
    form.reset(values);
    toast({ title: "Ödeme kaydedildi", tone: "success" });
    router.push("/payments");
  };

  return (
    <AppForm form={form} onSubmit={onSubmit} className="max-w-xl space-y-4">
      <FormRootError />
      <FormSectionTabs sections={SECTIONS} active={section} onChange={setSection} />

      {section === "customer" ? (
        <FormSectionPanel title="Müşteri">
          <Select
            label="Müşteri *"
            placeholder="Seçin"
            options={customers.map((c) => ({ value: String(c.id), label: c.name }))}
            error={errors.customer?.message}
            {...register("customer")}
          />
          {selected ? (
            <div className="mt-3">
              <PaymentFinancialHint openBalance={selected.open_balance} amount={amount} />
            </div>
          ) : null}
        </FormSectionPanel>
      ) : null}

      {section === "payment" ? (
        <FormSectionPanel title="Ödeme bilgileri">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Tarih *"
              type="date"
              error={errors.payment_date?.message}
              {...register("payment_date")}
            />
            <Input
              label="Tutar *"
              inputMode="decimal"
              error={errors.amount?.message}
              {...register("amount")}
            />
            <div className="sm:col-span-2">
              <Input
                label="Referans"
                error={errors.reference?.message}
                {...register("reference")}
              />
            </div>
          </div>
          {selected ? (
            <div className="mt-3">
              <PaymentFinancialHint openBalance={selected.open_balance} amount={amount} />
            </div>
          ) : null}
        </FormSectionPanel>
      ) : null}

      {section === "notes" ? (
        <FormSectionPanel title="Notlar">
          <Input label="Not" error={errors.notes?.message} {...register("notes")} />
        </FormSectionPanel>
      ) : null}

      <div className="flex gap-2">
        <SubmitButton>Kaydet</SubmitButton>
        <Button
          type="button"
          variant="secondary"
          disabled={isSubmitting}
          onClick={() => router.push("/payments")}
        >
          İptal
        </Button>
      </div>
    </AppForm>
  );
}
