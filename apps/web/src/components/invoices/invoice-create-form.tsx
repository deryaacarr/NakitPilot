"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { z } from "zod";

import { AppForm, FormRootError, SubmitButton } from "@/components/forms";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/datepicker";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import { createInvoice } from "@/lib/invoices/api";
import { invoiceCreateSchema, sumMoney } from "@/lib/invoices/form-schema";
import { applyBackendFieldErrors, useAppForm } from "@/lib/forms";

type FormValues = z.infer<typeof invoiceCreateSchema>;

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysISO(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function InvoiceCreateForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Array<{ id: number; name: string }>>([]);

  const form = useAppForm({
    schema: invoiceCreateSchema,
    defaultValues: {
      customer: "",
      number: "",
      invoice_date: todayISO(),
      due_date: addDaysISO(30),
      currency: "TRY",
      subtotal_amount: "0.00",
      tax_amount: "0.00",
      total_amount: "0.00",
      description: "",
    },
  });

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      const result = await listCustomers({ page_size: 100, is_active: "true" });
      if (cancelled || !result.ok) return;
      setCustomers(result.data.results.map((c) => ({ id: c.id, name: c.name })));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const {
    register,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = form;

  const syncTotal = () => {
    const { subtotal_amount, tax_amount } = getValues();
    setValue("total_amount", sumMoney(subtotal_amount, tax_amount), { shouldDirty: true });
  };

  const onSubmit = async (values: FormValues) => {
    const total = sumMoney(values.subtotal_amount, values.tax_amount);
    const result = await createInvoice({
      customer: Number(values.customer),
      number: values.number,
      invoice_date: values.invoice_date,
      due_date: values.due_date,
      currency: values.currency.toUpperCase(),
      subtotal_amount: values.subtotal_amount,
      tax_amount: values.tax_amount,
      total_amount: total,
      description: values.description,
      status: "OPEN",
    });

    if (!result.ok) {
      applyBackendFieldErrors(form.setError, result.error);
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }

    form.reset(values);
    toast({ title: "Fatura oluşturuldu", tone: "success" });
    router.push(`/invoices/${result.data.id}`);
    router.refresh();
  };

  return (
    <AppForm form={form} onSubmit={onSubmit} className="space-y-4">
      <FormRootError />
      <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <Select
          label="Müşteri"
          placeholder="Seçiniz"
          options={customers.map((c) => ({ value: String(c.id), label: c.name }))}
          error={errors.customer?.message}
          {...register("customer")}
        />
        <Input label="Fatura numarası" error={errors.number?.message} {...register("number")} />
        <DatePicker
          label="Fatura tarihi"
          error={errors.invoice_date?.message}
          {...register("invoice_date")}
        />
        <DatePicker
          label="Vade tarihi"
          error={errors.due_date?.message}
          {...register("due_date")}
        />
        <Input label="Para birimi" error={errors.currency?.message} {...register("currency")} />
        <Input
          label="Ara toplam"
          error={errors.subtotal_amount?.message}
          {...register("subtotal_amount", { onBlur: syncTotal })}
        />
        <Input
          label="Vergi"
          error={errors.tax_amount?.message}
          {...register("tax_amount", { onBlur: syncTotal })}
        />
        <Input label="Toplam" error={errors.total_amount?.message} {...register("total_amount")} />
        <div className="md:col-span-2">
          <Textarea
            label="Açıklama"
            rows={4}
            error={errors.description?.message}
            {...register("description")}
          />
        </div>
      </div>
      <div className="flex gap-2">
        <SubmitButton>Kaydet</SubmitButton>
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
  );
}
