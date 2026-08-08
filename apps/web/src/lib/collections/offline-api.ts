import { apiRequest } from "@/lib/api/client";

import type { OfflineQueueItem } from "@/lib/pwa/offline-queue";

export type OfflineSyncConflict = {
  client_id: string;
  status: "conflict";
  reason: string;
  server?: Record<string, unknown>;
};

export type OfflineSyncResult = {
  synced: Array<Record<string, unknown>>;
  conflicts: OfflineSyncConflict[];
  results: Array<Record<string, unknown>>;
};

export function syncOfflineQueue(items: OfflineQueueItem[]) {
  return apiRequest<OfflineSyncResult>("/api/collection-tasks/offline-sync/", {
    method: "POST",
    body: {
      items: items.map((item) => ({
        client_id: item.client_id,
        kind: item.kind,
        task_id: item.task_id,
        customer_id: item.customer_id,
        payload: item.payload,
        base_updated_at: item.base_updated_at,
        client_updated_at: item.client_updated_at,
      })),
    },
  });
}
