import { apiRequest } from "@/lib/api/client";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

export async function subscribeWebPush(): Promise<boolean> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return false;
  }
  const keyRes = await apiRequest<{ public_key: string }>("/api/notifications/push/vapid-public-key/");
  if (!keyRes.ok || !keyRes.data.public_key) {
    // Still request notification permission for local/testing without VAPID
    if (Notification.permission === "default") {
      await Notification.requestPermission();
    }
    return false;
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return false;
  const registration = await navigator.serviceWorker.ready;
  const sub = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(keyRes.data.public_key) as BufferSource,
  });
  const json = sub.toJSON();
  const result = await apiRequest("/api/notifications/push/subscribe/", {
    method: "POST",
    body: {
      endpoint: json.endpoint,
      keys: json.keys,
    },
  });
  return result.ok;
}
