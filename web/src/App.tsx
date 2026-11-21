import { lazy, Suspense } from "react";
import { navigateWorkspace, useWorkspaceQuery } from "./workspaceNavigation";
import type { IntakePage } from "./IntakeWorkbench";
import { WorkbenchShell } from "./WorkbenchShell";

const ManagedFeeds = lazy(() => import("./ManagedFeeds").then(m => ({ default: m.ManagedFeeds })));
const ReconciliationWorkspace = lazy(() => import("./ReconciliationWorkspace").then(m => ({ default: m.ReconciliationWorkspace })));
const RemediationWorkspace = lazy(() => import("./RemediationWorkspace").then(m => ({ default: m.RemediationWorkspace })));
const IntakeWorkbench = lazy(() => import("./IntakeWorkbench").then(m => ({ default: m.IntakeWorkbench })));
const ReviewConsole = lazy(() => import("./ReviewConsole").then(m => ({ default: m.ReviewConsole })));

export function App() {
  const query = useWorkspaceQuery();
  const requestedView = query.get("view");
  const workspace = requestedView && ["intake", "feeds", "reconciliation", "work", "sources", "qa", "remediation"].includes(requestedView) ? requestedView : "work";
  const navigate = (view: string) => navigateWorkspace(view);
  return (
    <WorkbenchShell workspace={workspace}>
      <Suspense fallback={<div role="status" className="loading">Loading workspace…</div>}>
      {["intake", "work", "sources"].includes(workspace) ? (
        <IntakeWorkbench page={workspace as IntakePage} />
      ) : workspace === "feeds" ? (
        <ManagedFeeds />
      ) : workspace === "reconciliation" ? (
        <ReconciliationWorkspace />
      ) : workspace === "remediation" ? (
        <RemediationWorkspace onExit={() => navigate("qa")} />
      ) : (
        <ReviewConsole onOpenRemediation={() => navigate("remediation")} />
      )}
      </Suspense>
    </WorkbenchShell>
  );
}
