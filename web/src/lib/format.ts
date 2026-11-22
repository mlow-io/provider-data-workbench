const CLINIC_LABELS: Record<string, string> = {
  "NASH-MAIN": "Nashville Midtown Clinic",
  "FRNK-WEST": "Franklin Cool Springs Clinic",
  "BRNT-PARK": "Brentwood Maryland Farms",
  "MURF-EAST": "Murfreesboro Medical Plaza",
  "HEND-LAKE": "Hendersonville Indian Lake",
};

export function isValidNpi(value: string | null | undefined): boolean {
  if (!value || !/^\d{10}$/.test(value)) return false;
  const digits = `80840${value.slice(0, 9)}`.split("").map(Number);
  let total = 0;
  for (let i = digits.length - 1, pos = 0; i >= 0; i -= 1, pos += 1) {
    let digit = digits[i];
    if (pos % 2 === 0) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    total += digit;
  }
  const check = (10 - (total % 10)) % 10;
  return check === Number(value[9]);
}

export function formatPhone(raw: string | null | undefined, ext?: string | null): string {
  if (!raw) return "Not supplied";
  const digits = raw.replace(/\D/g, "");
  const ten = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
  const formatted =
    ten.length === 10
      ? `(${ten.slice(0, 3)}) ${ten.slice(3, 6)}-${ten.slice(6)}`
      : raw;
  return ext ? `${formatted} ext. ${ext}` : formatted;
}

export function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

export function extractLocationCode(rawLocation: string | null | undefined): string {
  if (!rawLocation) return "UNASSIGNED";
  return rawLocation.includes(":") ? rawLocation.split(":", 2)[1] : rawLocation;
}

export function clinicDisplayName(codeOrRaw: string | null | undefined): string {
  const code = extractLocationCode(codeOrRaw);
  return CLINIC_LABELS[code] ?? code;
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "New",
    triaged: "Triaged",
    approved: "Approved",
    pending_verification: "Awaiting Verification",
    needs_information: "Needs Info",
    verified: "Verified",
    resolved: "Resolved",
    deferred: "Deferred",
    reopened: "Reopened",
    candidate: "Held Candidate",
    rejected: "Rejected",
    exact: "Exact Match",
    compatible_with_drift: "Drifted Match",
    ambiguous: "Ambiguous Match",
    unknown: "Unmapped Schema",
  };
  return labels[status] ?? status.replace(/_/g, " ");
}

export function riskLabel(risk: string): string {
  const labels: Record<string, string> = {
    high: "High",
    medium: "Medium",
    low: "Low",
  };
  return labels[risk] ?? risk;
}

export function daysUntilNsaCheck(verifiedIso: string | null | undefined): {
  daysAgo: number;
  compliant: boolean;
} {
  if (!verifiedIso) return { daysAgo: 99, compliant: false };
  const parsed = new Date(verifiedIso);
  if (Number.isNaN(parsed.getTime())) return { daysAgo: 0, compliant: true };
  const diffMs = Math.max(0, Date.now() - parsed.getTime());
  const daysAgo = Math.floor(diffMs / 86_400_000);
  return { daysAgo, compliant: daysAgo <= 90 };
}

export function triggerDownload(filename: string, content: BlobPart, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
