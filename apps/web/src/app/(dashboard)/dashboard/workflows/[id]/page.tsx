import { WorkflowBuilderView } from "@/components/workflows/workflow-builder-view";

export default async function WorkflowBuilderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="space-y-4">
      <div>
        <a href="/dashboard/workflows" className="text-sm text-teal-800 hover:underline">
          ← İş akışları
        </a>
        <h1 className="mt-2 font-serif text-3xl tracking-tight text-slate-900">Akış düzenleyici</h1>
      </div>
      <WorkflowBuilderView workflowId={id} />
    </div>
  );
}
