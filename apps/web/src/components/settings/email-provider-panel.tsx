"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { fetchEmailProviderConfig, saveEmailProviderConfig } from "@/lib/messages/api";
import type { EmailProviderConfig } from "@/lib/messages/types";

export function EmailProviderPanel() {
  const { toast } = useToast();
  const [config, setConfig] = useState<EmailProviderConfig | null>(null);
  const [fromEmail, setFromEmail] = useState("");
  const [fromName, setFromName] = useState("");
  const [provider, setProvider] = useState("SMTP");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void fetchEmailProviderConfig().then((result) => {
      if (!result.ok) return;
      setConfig(result.data);
      if (result.data.configured) {
        setFromEmail(result.data.from_email || "");
        setFromName(result.data.from_name || "");
        setProvider(result.data.provider || "SMTP");
        setSmtpHost(result.data.smtp_host || "");
        setSmtpPort(result.data.smtp_port || 587);
      }
    });
  }, []);

  const onSave = async () => {
    setSaving(true);
    const result = await saveEmailProviderConfig({
      provider,
      from_email: fromEmail,
      from_name: fromName,
      smtp_host: smtpHost,
      smtp_port: smtpPort,
      smtp_use_tls: true,
      username: username || undefined,
      password: password || undefined,
    });
    setSaving(false);
    if (!result.ok) {
      toast({ title: result.error.title, description: result.error.message, tone: "error" });
      return;
    }
    setConfig(result.data);
    setPassword("");
    toast({ title: "E-posta ayarları kaydedildi", tone: "success" });
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">E-posta sağlayıcı (SMTP / API)</h2>
      <p className="mt-1 text-xs text-slate-500">
        Kimlik bilgileri şifreli saklanır. Gönderim kullanıcı onayı ile yapılır.
        {config?.has_credentials ? ` · kayıtlı: …${config.key_hint}` : ""}
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">Sağlayıcı</span>
          <select
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="SMTP">SMTP</option>
            <option value="API">Sağlayıcı API</option>
            <option value="CONSOLE">Konsol (geliştirme)</option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">Gönderen e-posta</span>
          <input
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={fromEmail}
            onChange={(e) => setFromEmail(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">Gönderen adı</span>
          <input
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={fromName}
            onChange={(e) => setFromName(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">SMTP host</span>
          <input
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={smtpHost}
            onChange={(e) => setSmtpHost(e.target.value)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">SMTP port</span>
          <input
            type="number"
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={smtpPort}
            onChange={(e) => setSmtpPort(Number(e.target.value) || 587)}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-slate-500">Kullanıcı adı</span>
          <input
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="block text-sm sm:col-span-2">
          <span className="mb-1 block text-slate-500">Şifre / API anahtarı</span>
          <input
            type="password"
            className="h-10 w-full rounded-lg border border-slate-300 px-3"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            placeholder="Değiştirmek için yeni değer girin"
          />
        </label>
      </div>
      <div className="mt-4 flex justify-end">
        <Button onClick={() => void onSave()} loading={saving} disabled={!fromEmail}>
          Kaydet
        </Button>
      </div>
    </section>
  );
}
