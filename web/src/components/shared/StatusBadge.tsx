import { Badge } from "@/components/ui/badge";
import { riskLabel, statusLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone =
    status === "verified" || status === "resolved" || status === "approved" || status === "exact"
      ? "bg-status-success-bg text-status-success border-transparent"
      : status === "candidate" ||
          status === "triaged" ||
          status === "pending_verification" ||
          status === "needs_information" ||
          status === "compatible_with_drift"
        ? "bg-status-warning-bg text-status-warning border-transparent"
        : status === "rejected" || status === "reopened" || status === "held" || status === "unknown"
          ? "bg-status-danger-bg text-status-danger border-transparent"
          : "bg-secondary text-secondary-foreground border-transparent";

  return (
    <Badge variant="outline" className={cn("font-medium", tone)}>
      {label ?? statusLabel(status)}
    </Badge>
  );
}

export function RiskBadge({ risk }: { risk: string }) {
  const tone =
    risk === "high"
      ? "bg-status-danger-bg text-status-danger border-transparent"
      : risk === "medium"
        ? "bg-status-warning-bg text-status-warning border-transparent"
        : "bg-secondary text-secondary-foreground border-transparent";

  return (
    <Badge variant="outline" className={cn("font-medium", tone)}>
      {riskLabel(risk)}
    </Badge>
  );
}
