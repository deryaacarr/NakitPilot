/** NP-342 — IndexedDB-backed offline field queue */

export type OfflineKind = "NOTE" | "COMPLETE_TASK" | "PROMISE_DRAFT";

export type OfflineQueueItem = {
  client_id: string;
  kind: OfflineKind;
  task_id?: number | null;
  customer_id?: number | null;
  payload: Record<string, unknown>;
  base_updated_at?: string | null;
  client_updated_at: string;
  created_at: string;
};

const DB_NAME = "nakitpilot-offline";
const STORE = "queue";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "client_id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function enqueueOffline(item: Omit<OfflineQueueItem, "created_at" | "client_updated_at"> & {
  client_updated_at?: string;
}): Promise<OfflineQueueItem> {
  const full: OfflineQueueItem = {
    ...item,
    client_updated_at: item.client_updated_at || new Date().toISOString(),
    created_at: new Date().toISOString(),
  };
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(full);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
  return full;
}

export async function listOfflineQueue(): Promise<OfflineQueueItem[]> {
  const db = await openDb();
  const rows = await new Promise<OfflineQueueItem[]>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result as OfflineQueueItem[]);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return rows.sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export async function removeOfflineItems(clientIds: string[]): Promise<void> {
  if (!clientIds.length) return;
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    const store = tx.objectStore(STORE);
    for (const id of clientIds) store.delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `offline-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
