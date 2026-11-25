import type { CSSProperties, ReactNode } from "react";
import {
  BriefcaseBusiness,
  Building2,
  FileSpreadsheet,
  GitCompareArrows,
  PhoneCall,
  RotateCcw,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { WorkspaceView } from "@/lib/types";
import { navigateWorkspace, workspaceHref } from "@/workspaceNavigation";

interface NavItem {
  view: WorkspaceView;
  label: string;
  icon: typeof BriefcaseBusiness;
  badge?: number;
}

interface AppShellProps {
  workspace: WorkspaceView;
  openDiscrepancies?: number;
  heldDeliveries?: number;
  demoMode: boolean;
  onResetDemo?: () => void;
  children: ReactNode;
}

function AppSidebar({
  workspace,
  openDiscrepancies,
  heldDeliveries,
  demoMode,
}: Omit<AppShellProps, "children" | "onResetDemo">) {
  const { setOpenMobile } = useSidebar();
  const triageItems: NavItem[] = [
    {
      view: "work",
      label: "Work Queue",
      icon: BriefcaseBusiness,
      badge: openDiscrepancies,
    },
    {
      view: "corrections",
      label: "Phone Corrections",
      icon: PhoneCall,
    },
    {
      view: "deliveries",
      label: "Deliveries & Export",
      icon: GitCompareArrows,
      badge: heldDeliveries,
    },
  ];
  const directoryItems: NavItem[] = [
    {
      view: "intake",
      label: "Import & Adapt",
      icon: FileSpreadsheet,
    },
    {
      view: "directory",
      label: "Provider Directory",
      icon: Building2,
    },
  ];

  function renderNavItems(items: NavItem[]) {
    return items.map((item) => (
      <SidebarMenuItem key={item.view}>
        <SidebarMenuButton
          asChild
          isActive={workspace === item.view}
          tooltip={item.label}
        >
          <a
            href={workspaceHref(item.view)}
            onClick={(event) => {
              if (
                event.button === 0 &&
                !event.ctrlKey &&
                !event.metaKey &&
                !event.shiftKey &&
                !event.altKey
              ) {
                event.preventDefault();
                navigateWorkspace(item.view);
                setOpenMobile(false);
              }
            }}
          >
            <item.icon />
            <span>{item.label}</span>
          </a>
        </SidebarMenuButton>
        {typeof item.badge === "number" && item.badge > 0 && (
          <SidebarMenuBadge>{item.badge}</SidebarMenuBadge>
        )}
      </SidebarMenuItem>
    ));
  }

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="border-b px-3 py-3">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Stethoscope className="size-4" />
          </div>
          <div className="flex min-w-0 flex-col group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-semibold tracking-tight text-foreground">
              Provider Workbench
            </span>
            <span className="truncate text-xs text-muted-foreground">
              Middle TN Directory Ops
            </span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Triage & Ops</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{renderNavItems(triageItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Data & Directory</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{renderNavItems(directoryItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t p-3 group-data-[collapsible=icon]:hidden">
        <div className="flex items-start gap-2 rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="flex flex-col gap-0.5">
            <span className="font-medium text-foreground">
              {demoMode ? "Static Demo Sandbox" : "SQLite + Intake Engine"}
            </span>
            <span>Synthetic TN data · Audit trail enabled</span>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

const VIEW_TITLES: Record<WorkspaceView, string> = {
  work: "Work Queue",
  intake: "Import & Adapt",
  corrections: "Phone Corrections",
  deliveries: "Deliveries & Export",
  directory: "Provider Directory",
};

export function AppShell({
  workspace,
  openDiscrepancies,
  heldDeliveries,
  demoMode,
  onResetDemo,
  children,
}: AppShellProps) {
  return (
    <TooltipProvider>
      <SidebarProvider style={{ "--sidebar-width": "15.5rem" } as CSSProperties}>
        <AppSidebar
          workspace={workspace}
          openDiscrepancies={openDiscrepancies}
          heldDeliveries={heldDeliveries}
          demoMode={demoMode}
        />
        <SidebarInset className="min-w-0">
          <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-4 border-b bg-card px-4 md:rounded-t-xl lg:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <SidebarTrigger aria-label="Toggle navigation" />
              <Separator orientation="vertical" className="h-4" />
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem className="hidden sm:inline-flex">
                    Cumberland Valley Ops
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className="hidden sm:inline-flex" />
                  <BreadcrumbItem>
                    <BreadcrumbPage>{VIEW_TITLES[workspace]}</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="hidden sm:inline-flex">
                {demoMode ? "Interactive Demo · Synthetic TN" : "Local Workspace · Live API"}
              </Badge>
              {demoMode && onResetDemo && (
                <Button variant="outline" size="sm" onClick={onResetDemo}>
                  <RotateCcw data-icon="inline-start" />
                  Reset Demo
                </Button>
              )}
            </div>
          </header>
          <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-4 lg:p-6">
            {children}
          </main>
        </SidebarInset>
        <Toaster />
      </SidebarProvider>
    </TooltipProvider>
  );
}
