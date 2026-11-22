import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { dataClient } from "@/lib/dataClient";
import type { WorkspaceView } from "@/lib/types";
import { DeliveriesPage } from "@/pages/DeliveriesPage";
import { ImportAdaptPage } from "@/pages/ImportAdaptPage";
import { PhoneCorrectionsPage } from "@/pages/PhoneCorrectionsPage";
import { ProviderDirectoryPage } from "@/pages/ProviderDirectoryPage";
import { WorkQueuePage } from "@/pages/WorkQueuePage";
import { useWorkspaceQuery } from "@/workspaceNavigation";

const VIEWS: WorkspaceView[] = ["work", "intake", "corrections", "deliveries", "directory"];

export function App() {
  const queryClient = useQueryClient();
  const query = useWorkspaceQuery();
  const requested = query.get("view") as WorkspaceView | null;
  const workspace: WorkspaceView =
    requested && VIEWS.includes(requested) ? requested : "work";

  const overviewQuery = useQuery({
    queryKey: ["workbench-overview"],
    queryFn: () => dataClient.overview(),
  });

  async function handleResetDemo() {
    dataClient.resetDemo();
    await queryClient.invalidateQueries();
    toast.success("Demo workspace reset to initial Middle Tennessee state");
  }

  return (
    <AppShell
      workspace={workspace}
      openDiscrepancies={overviewQuery.data?.open_discrepancies}
      heldDeliveries={overviewQuery.data?.held_deliveries}
      demoMode={dataClient.isDemoMode()}
      onResetDemo={handleResetDemo}
    >
      {workspace === "work" ? (
        <WorkQueuePage />
      ) : workspace === "intake" ? (
        <ImportAdaptPage />
      ) : workspace === "corrections" ? (
        <PhoneCorrectionsPage />
      ) : workspace === "deliveries" ? (
        <DeliveriesPage />
      ) : (
        <ProviderDirectoryPage />
      )}
    </AppShell>
  );
}
