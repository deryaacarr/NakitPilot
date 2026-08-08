"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { applyWaitingServiceWorker, registerServiceWorker } from "@/lib/pwa/register";

export function PwaProvider() {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [updateReady, setUpdateReady] = useState(false);
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    void registerServiceWorker({
      onUpdateAvailable: (reg) => {
        setRegistration(reg);
        setUpdateReady(true);
      },
    });

    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  }, []);

  return (
    <>
      {updateReady ? (
        <div className="fixed inset-x-0 bottom-0 z-[60] border-t border-slate-200 bg-white p-3 shadow-lg sm:bottom-4 sm:left-auto sm:right-4 sm:max-w-sm sm:rounded-xl sm:border">
          <p className="text-sm font-medium text-slate-900">Uygulama güncellemesi hazır</p>
          <p className="mt-0.5 text-xs text-slate-600">Yeni sürümü yüklemek için yenileyin.</p>
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                if (registration) applyWaitingServiceWorker(registration);
                window.location.reload();
              }}
            >
              Güncelle
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setUpdateReady(false)}>
              Sonra
            </Button>
          </div>
        </div>
      ) : null}
      {installEvent ? (
        <div className="fixed inset-x-0 bottom-0 z-[55] border-t border-slate-200 bg-slate-900 p-3 text-white sm:bottom-4 sm:left-4 sm:max-w-xs sm:rounded-xl">
          <p className="text-sm font-medium">Ana ekrana ekle</p>
          <p className="mt-0.5 text-xs text-slate-300">Saha kullanımı için NakitPilot’u yükleyin.</p>
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              onClick={async () => {
                await installEvent.prompt();
                setInstallEvent(null);
              }}
            >
              Yükle
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-white"
              onClick={() => setInstallEvent(null)}
            >
              Kapat
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}
