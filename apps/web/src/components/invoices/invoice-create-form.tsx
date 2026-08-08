"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

import {
  AppForm,
  FormRootError,
  FormSectionPanel,
  FormSectionTabs,
  InvoiceFinancialHint,
  SubmitButton,
} from "@/components/forms";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/datepicker";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { listCustomers } from "@/lib/customers/api";
import type { Customer } from "@/lib/customers/types";
import { createInvoice } from "@/lib/invoices/api";
import { addDaysISO, invoiceCreateSchema, sumMoney } from "@/lib/invoices/form-schema";
import { applyBackendFieldErrors, useAppForm } from "@/lib/forms";

type FormValues = z.infer<typeof invoiceCreateSchema>;
type SectionId = "customer" | "dates" | "amounts" | "notes";

const SECTIONS: { id: SectionId; label: string }[] = [
  { id: "customer", label: "Müşteri" },
  { id: "dates", label: "Tarihler" },
  { id: "amounts", label: "Tutarlar" },
  { id: "notes", label: "Açıklama" },
];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function InvoiceCreateForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [section, setSection] = useState<SectionId>("customer");

  const form = useAppForm({
    schema: invoiceCreateSchema,
    defaultValues: {
      customer: "",
      number: "",
      invoice_date: todayISO(),
      due_date: addDaysISO(todayISO(), 30),
      currency: "TRY",
      subtotal_amount: "0.00",
      tax_amount: "0.00",
      total_amount: "0.00",
      description: "",
    },
  });

  useEffect(() => {
    let cancelled = false;
    void listCustomers({ page_size: 100, is_active: "true" }).then((result) => {
      if (cancelled || !result.ok) return;
      setCustomers(result.data.results || []);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const {
    register,
    setValue,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = form;

  const customerId = watch("customer");
  const invoiceDate = watch("invoice_date");
  const selected = useMemo(
    () => customers.find((c) => String(c.id) === customerId) || null,
    [customers, customerId],
  );
  const suggestedDue = useMemo(() => {
    if (!selected || !invoiceDate) return null;
    return addDaysISO(invoiceDate, selected.payment_term_days ?? 30);
  }, [selected, invoiceDate]);

  const syncTotal = () => {
    const { subtotal_amount, tax_amount } = getValues();
    setValue("total_amount", sumMoney(subtotal_amount, tax_amount), { shouldDirty: true });
  };

  const onCustomerChange = (id: string) => {
    setValue("customer", id, { shouldValidate: true, shouldDirty: true });
    const c = customers.find((x) => String(x.id) === id);
    if (!c) return;
    const base = getValues("invoice_date") || todayISO();
    const due = addDaysISO(base, c.payment_term_days ?? 30);
    setValue("due_date", due, { shouldValidate: true, shouldDirty: true });
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

  const errorSections: Partial<Record<SectionId, boolean>> = {
    customer: Boolean(errors.customer || errors.number),
    dates: Boolean(errors.invoice_date || errors.due_date),
    amounts: Boolean(
      errors.subtotal_amount || errors.tax_amount || errors.total_amount || errors.currency,
    ),
    notes: Boolean(errors.description),
  };

  return (
    <AppForm form={form} onSubmit={onSubmit} className="space-y-4">
      <FormRootError />
      <FormSectionTabs
        sections={SECTIONS}
        active={section}
        onChange={setSection}
        errorSections={errorSections}
      />

      {section === "customer" ? (
        <FormSectionPanel title="Müşteri ve numara">
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Müşteri"
              placeholder="Seçiniz"
              options={customers.map((c) => ({ value: String(c.id), label: c.name }))}
              error={errors.customer?.message}
              value={customerId}
              onChange={(e) => onCustomerChange(e.target.value)}
              onBlur={() => void form.trigger("customer")}
              name="customer"
            />
            <Input label="Fatura numarası" error={errors.number?.message} {...register("number")} />
          </div>
          {selected ? (
            <div className="mt-3">
              <InvoiceFinancialHint
                paymentTermDays={selected.payment_term_days}
                suggestedDue={suggestedDue}
              />
            </div>
          ) : null}
        </FormSectionPanel>
      ) : null}

      {section === "dates" ? (
        <FormSectionPanel title="Tarihler">
          <div className="grid gap-4 md:grid-cols-2">
            <DatePicker
              label="Fatura tarihi"
              error={errors.invoice_date?.message}
              {...register("invoice_date", {
                onChange: (e) => {
                  const c = selected;
                  if (c) {
                    setValue("due_date", addDaysISO(e.target.value, c.payment_term_days ?? 30), {
                      shouldValidate: true,
                    });
                  }
                },
              })}
            />
            <DatePicker
              label="Vade tarihi"
              error={errors.due_date?.message}
              {...register("due_date")}
            />
          </div>
          {selected ? (
            <div className="mt-3">
              <InvoiceFinancialHint
                paymentTermDays={selected.payment_term_days}
                suggestedDue={suggestedDue}
              />
            </div>
          ) : null}
        </FormSectionPanel>
      ) : null}

      {section === "amounts" ? (
        <FormSectionPanel title="Tutarlar">
          <div className="grid gap-4 md:grid-cols-2">
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
            <Input
              label="Toplam"
              error={errors.total_amount?.message}
              {...register("total_amount")}
            />
          </div>
        </FormSectionPanel>
      ) : null}

      {section === "notes" ? (
        <FormSectionPanel title="Açıklama">
          <Textarea
            label="Açıklama"
            rows={4}
            error={errors.description?.message}
            {...register("description")}
          />
        </FormSectionPanel>
      ) : null}

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
