"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Surface } from "@/components/ui/surface";
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
    <Surface as="section">
      <h2 className="text-sm font-semibold text-foreground">E-posta sağlayıcı (SMTP / API)</h2>
      <p className="mt-1 text-xs text-muted">
        Kimlik bilgileri şifreli saklanır. Gönderim kullanıcı onayı ile yapılır.
        {config?.has_credentials ? ` · kayıtlı: …${config.key_hint}` : ""}
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Select
          label="Sağlayıcı"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          options={[
            { value: "SMTP", label: "SMTP" },
            { value: "API", label: "Sağlayıcı API" },
            { value: "CONSOLE", label: "Konsol (geliştirme)" },
          ]}
        />
        <Input
          label="Gönderen e-posta"
          value={fromEmail}
          onChange={(e) => setFromEmail(e.target.value)}
        />
        <Input
          label="Gönderen adı"
          value={fromName}
          onChange={(e) => setFromName(e.target.value)}
        />
        <Input
          label="SMTP host"
          value={smtpHost}
          onChange={(e) => setSmtpHost(e.target.value)}
        />
        <Input
          label="SMTP port"
          type="number"
          value={smtpPort}
          onChange={(e) => setSmtpPort(Number(e.target.value) || 587)}
        />
        <Input
          label="Kullanıcı adı"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
        />
        <div className="sm:col-span-2">
          <Input
            label="Şifre / API anahtarı"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            placeholder="Değiştirmek için yeni değer girin"
          />
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button onClick={() => void onSave()} loading={saving} disabled={!fromEmail}>
          Kaydet
        </Button>
      </div>
    </Surface>
  );
}
