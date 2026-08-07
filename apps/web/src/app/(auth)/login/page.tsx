import type { Metadata } from "next";

import { LoginForm } from "@/components/auth/login-form";
import { env } from "@/lib/env";

export const metadata: Metadata = {
  title: "Giriş",
  description: `${env.appName} hesabınıza giriş yapın`,
};

export default function LoginPage() {
  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200/80 bg-white/90 p-8 shadow-[0_20px_50px_-28px_rgba(15,23,42,0.35)] backdrop-blur">
      <div className="mb-8 space-y-2">
        <p className="font-serif text-3xl tracking-tight text-slate-900">{env.appName}</p>
        <p className="text-sm leading-6 text-slate-600">
          Tahsilat operasyonunuza devam etmek için e-posta ve şifrenizle giriş yapın.
        </p>
      </div>
      <LoginForm />
    </div>
  );
}
