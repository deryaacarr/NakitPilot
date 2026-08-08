"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { apiRequest } from "@/lib/api/client";
import { updateCollectionTask } from "@/lib/collections/api";
import type { CollectionTask } from "@/lib/collections/types";

type MembershipRow = {
  user_id: number;
  user_email: string;
  user_name?: string;
  organization: number;
};

async function loadAssignees(): Promise<MembershipRow[]> {
  const memberships = await apiRequest<MembershipRow[]>("/api/memberships/me/");
  if (!memberships.ok || memberships.data.length === 0) return [];
  const orgId = memberships.data[0].organization;
  const orgMembers = await apiRequest<MembershipRow[] | { results?: MembershipRow[] }>(
    `/api/organizations/${orgId}/memberships/`,
  );
  if (!orgMembers.ok) return [];
  return Array.isArray(orgMembers.data)
    ? orgMembers.data
    : (orgMembers.data.results ?? []);
}

export function PostponeTaskModal({
  task,
  onClose,
  onDone,
}: {
  task: CollectionTask;
  onClose: () => void;
  onDone: () => void;
}) {
  const { toast } = useToast();
  const [dueDate, setDueDate] = useState(task.due_date.slice(0, 10));
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!dueDate) {
      toast({ title: "Yeni tarih gerekli", tone: "warning" });
      return;
    }
    setBusy(true);
    const res = await updateCollectionTask(task.id, { due_date: dueDate });
    setBusy(false);
    if (!res.ok) {
      toast({ title: "Ertelenemedi", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görev ertelendi", tone: "success" });
    onDone();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Görevi ertele"
      description={task.customer_name}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="button" loading={busy} onClick={() => void submit()}>
            Ertele
          </Button>
        </div>
      }
    >
      <Input
        label="Yeni vade *"
        type="date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
      />
    </Modal>
  );
}

export function AssignTaskModal({
  task,
  onClose,
  onDone,
}: {
  task: CollectionTask;
  onClose: () => void;
  onDone: () => void;
}) {
  const { toast } = useToast();
  const [assignees, setAssignees] = useState<MembershipRow[]>([]);
  const [userId, setUserId] = useState(task.assigned_to ? String(task.assigned_to) : "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadAssignees().then(setAssignees);
  }, []);

  async function submit() {
    if (!userId) {
      toast({ title: "Sorumlu seçin", tone: "warning" });
      return;
    }
    setBusy(true);
    const res = await updateCollectionTask(task.id, { assigned_to: Number(userId) });
    setBusy(false);
    if (!res.ok) {
      toast({ title: "Atama başarısız", description: res.error.message, tone: "error" });
      return;
    }
    toast({ title: "Görev atandı", tone: "success" });
    onDone();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Başkasına ata"
      description={task.customer_name}
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="button" loading={busy} onClick={() => void submit()}>
            Ata
          </Button>
        </div>
      }
    >
      <Select
        label="Sorumlu *"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
        options={[
          { value: "", label: "Seçin…" },
          ...assignees.map((m) => ({
            value: String(m.user_id),
            label: m.user_name || m.user_email,
          })),
        ]}
      />
    </Modal>
  );
}
