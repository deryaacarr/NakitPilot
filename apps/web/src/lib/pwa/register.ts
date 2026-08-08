/** NP-341 — register service worker + expose update callback */

export type SwRegistrationHandlers = {
  onUpdateAvailable?: (registration: ServiceWorkerRegistration) => void;
};

export async function registerServiceWorker(handlers: SwRegistrationHandlers = {}) {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }
  try {
    const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    if (registration.waiting) {
      handlers.onUpdateAvailable?.(registration);
    }
    registration.addEventListener("updatefound", () => {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener("statechange", () => {
        if (worker.state === "installed" && navigator.serviceWorker.controller) {
          handlers.onUpdateAvailable?.(registration);
        }
      });
    });
    return registration;
  } catch {
    return null;
  }
}

export function applyWaitingServiceWorker(registration: ServiceWorkerRegistration) {
  registration.waiting?.postMessage({ type: "SKIP_WAITING" });
}
