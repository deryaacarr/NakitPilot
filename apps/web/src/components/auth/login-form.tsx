"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { loginRequest } from "@/lib/auth/api";
import { type LoginErrorCode, loginErrorMessage } from "@/lib/auth/errors";

export const loginSchema = z.object({
  email: z.email("Geçerli bir e-posta girin"),
  password: z.string().min(1, "Şifre gerekli"),
  remember: z.boolean(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function safeNextPath(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) {
    return "/dashboard";
  }
  return raw;
}

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [hydrated, setHydrated] = useState(false);
  const [formError, setFormError] = useState<{
    code: LoginErrorCode;
    message: string;
  } | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", remember: true },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    const result = await loginRequest(values);
    if (!result.ok) {
      setFormError(result.error);
      return;
    }
    router.replace(safeNextPath(searchParams.get("next")));
    router.refresh();
  });

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-5"
      noValidate
      data-testid="login-form"
      data-hydrated={hydrated ? "true" : "false"}
    >
      <div className="space-y-2">
        <label htmlFor="email" className="block text-sm font-medium text-slate-700">
          E-posta
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.email) || formError?.code === "invalid_email"}
          className="focus:border-brand focus:ring-brand/20 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 transition outline-none focus:ring-2 disabled:opacity-60"
          {...register("email")}
        />
        {errors.email ? (
          <p className="text-sm text-red-700" role="alert">
            {errors.email.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <label htmlFor="password" className="block text-sm font-medium text-slate-700">
          Şifre
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.password) || formError?.code === "invalid_password"}
          className="focus:border-brand focus:ring-brand/20 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 transition outline-none focus:ring-2 disabled:opacity-60"
          {...register("password")}
        />
        {errors.password ? (
          <p className="text-sm text-red-700" role="alert">
            {errors.password.message}
          </p>
        ) : null}
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          disabled={isSubmitting}
          className="text-brand focus:ring-brand/30 size-4 rounded border-slate-300"
          {...register("remember")}
        />
        Beni hatırla
      </label>

      {formError ? (
        <div
          role="alert"
          data-error-code={formError.code}
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800"
        >
          {formError.message || loginErrorMessage(formError.code)}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="bg-brand text-brand-foreground inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isSubmitting ? (
          <span className="inline-flex items-center gap-2">
            <span
              aria-hidden
              className="border-brand-foreground/30 border-t-brand-foreground size-4 animate-spin rounded-full border-2"
            />
            Giriş yapılıyor…
          </span>
        ) : (
          "Giriş yap"
        )}
      </button>
    </form>
  );
}

export function LoginForm() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Form yükleniyor…</p>}>
      <LoginFormInner />
    </Suspense>
  );
}
