import type { CSSProperties, ReactNode } from "react";
import { BriefcaseBusiness, FileInput, FolderClock, GitCompareArrows, Library, ListChecks, ShieldCheck, Stethoscope } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarRail, SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { navigateWorkspace, workspaceHref } from "./workspaceNavigation";
import "./workbench-shell.css";

const daily = [
  { view: "work", label: "Work queue", detail: "Investigate and follow up", icon: BriefcaseBusiness },
  { view: "intake", label: "Receive data", detail: "Upload, map and review", icon: FileInput },
  { view: "feeds", label: "Deliveries", detail: "Review recurring datasets", icon: FolderClock },
  { view: "reconciliation", label: "Provider records", detail: "Link identities and compare", icon: Stethoscope },
];
const tools = [
  { view: "sources", label: "Sources", detail: "Capture and source history", icon: Library },
  { view: "qa", label: "Legacy QA", detail: "Original batch review", icon: ListChecks },
  { view: "remediation", label: "Corrections", detail: "Original correction loop", icon: GitCompareArrows },
];

function WorkbenchNavigation({ workspace }: { workspace: string }) {
  const { setOpenMobile } = useSidebar();
  function group(items: typeof daily, title: string) {
    return <SidebarGroup>
      <SidebarGroupLabel>{title}</SidebarGroupLabel>
      <SidebarGroupContent><SidebarMenu>{items.map(item => <SidebarMenuItem key={item.view}>
        <SidebarMenuButton asChild isActive={workspace === item.view} tooltip={item.label} size="lg">
          <a href={workspaceHref(item.view)} aria-label={item.label} aria-current={workspace === item.view ? "page" : undefined}
            onClick={event => {
              if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
                event.preventDefault();
                navigateWorkspace(item.view);
                setOpenMobile(false);
              }
            }}>
            <item.icon aria-hidden="true" />
            <span className="wb-nav-copy"><span>{item.label}</span><small aria-hidden="true">{item.detail}</small></span>
          </a>
        </SidebarMenuButton>
      </SidebarMenuItem>)}</SidebarMenu></SidebarGroupContent>
    </SidebarGroup>;
  }
  return <Sidebar collapsible="icon" className="wb-sidebar">
    <SidebarHeader>
      <div className="wb-brand"><span className="wb-brand-mark" aria-hidden="true">pd<span>/</span></span><strong>Provider Directory<span>Workbench</span></strong></div>
    </SidebarHeader>
    <SidebarContent><nav aria-label="Workbench navigation">{group(daily, "Daily work")}{group(tools, "Sources & supporting tools")}</nav></SidebarContent>
    <SidebarFooter><div className="wb-local"><ShieldCheck aria-hidden="true" /><span>Local workspace<small>Decisions and evidence retained.</small></span></div></SidebarFooter>
    <SidebarRail />
  </Sidebar>;
}

export function WorkbenchShell({ workspace, children }: { workspace: string; children: ReactNode }) {
  const current = [...daily, ...tools].find(item => item.view === workspace) ?? daily[0];
  return <TooltipProvider><SidebarProvider className="wb-app" style={{ "--sidebar-width": "15.5rem" } as CSSProperties}>
    <a className="wb-skip" href="#workspace-content">Skip to workspace</a>
    <WorkbenchNavigation workspace={workspace} />
    <SidebarInset className="wb-content">
      <header className="wb-context">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger aria-label="Toggle navigation" />
          <Separator orientation="vertical" className="h-5" />
          <Breadcrumb><BreadcrumbList><BreadcrumbItem className="hidden sm:block">Provider operations</BreadcrumbItem><BreadcrumbSeparator className="hidden sm:block" /><BreadcrumbItem><BreadcrumbPage>{current.label}</BreadcrumbPage></BreadcrumbItem></BreadcrumbList></Breadcrumb>
        </div>
        <Badge variant="outline" className="wb-local-label">Single-user workspace</Badge>
      </header>
      <div id="workspace-content" tabIndex={-1}>{children}</div>
    </SidebarInset>
  </SidebarProvider></TooltipProvider>;
}
