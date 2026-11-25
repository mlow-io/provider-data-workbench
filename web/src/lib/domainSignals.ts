export interface RegulatoryRegimeInfo {
  regime:
    | "commercial_nsa"
    | "medicare_advantage"
    | "medicaid_mco"
    | "delegated_dental_vision"
    | "unclassified_regime";
  label: string;
  sla_note: string;
}

export interface PhoneConflictInfo {
  category:
    | "exact_match"
    | "toll_free_centralized_line"
    | "same_npa_nxx_clinic_pbx"
    | "same_area_code_different_exchange"
    | "different_area_code_or_state"
    | "missing_phone";
  label: string;
  guidance: string;
}

export interface FourGateEvidence {
  gate1_identity: { status: string; label: string; source: string };
  gate2_licensure: { status: string; label: string; psv_required: boolean; note: string };
  gate3_enrollment: { status: string; leie_clear: boolean; label: string; note: string };
  gate4_directory: { address_confirmed: boolean; hospital_based_newpt_leak: boolean; label: string; note: string };
}

const HOSPITAL_BASED_PREFIXES = ["2085R", "207L", "207P", "207Z", "208M", "367500"];
const HOSPITAL_BASED_KEYWORDS = [
  "radiology",
  "anesthesiology",
  "emergency medicine",
  "pathology",
  "hospitalist",
  "crna",
  "nurse anesthetist",
];
const TOLL_FREE_CODES = new Set(["800", "888", "877", "866", "855", "844", "833"]);

export function isHospitalBasedTaxonomy(specialty: string | null | undefined): boolean {
  if (!specialty) return false;
  const trimmed = specialty.trim();
  const token = (trimmed.split(/\s+/)[0] ?? "").toUpperCase();
  if (HOSPITAL_BASED_PREFIXES.some((p) => token.startsWith(p))) return true;
  const low = trimmed.toLowerCase();
  return HOSPITAL_BASED_KEYWORDS.some((kw) => low.includes(kw));
}

export function classifyRegulatoryRegime(networkOrSource: string | null | undefined): RegulatoryRegimeInfo {
  const text = (networkOrSource ?? "").trim().toLowerCase();
  if (["tenncare", "medicaid", "community plan", "chip"].some((k) => text.includes(k))) {
    return {
      regime: "medicaid_mco",
      label: "Medicaid / TennCare MCO",
      sla_note: "Governed by state Medicaid MCO network-adequacy & CMS Medicaid managed-care directory standards.",
    };
  }
  if (["medicare advantage", "midsouth", "d-snp", "c-snp", "dual complete", "ma ", "ma-", "-ma"].some((k) => text.includes(k))) {
    return {
      regime: "medicare_advantage",
      label: "CMS Medicare Advantage",
      sla_note: "Subject to CMS Medicare Advantage directory accuracy oversight & REAL Health Providers Act cadence.",
    };
  }
  if (["dental", "vision", "fedvip", "optometry", "spectera", "healthplex"].some((k) => text.includes(k))) {
    return {
      regime: "delegated_dental_vision",
      label: "Delegated Dental / Vision",
      sla_note: "Routed via delegated specialty hubs; audit for multi-site corporate address fan-out.",
    };
  }
  if (["commercial", "ppo", "epo", "hmo", "erisa", "volunteer", "choice", "options"].some((k) => text.includes(k))) {
    return {
      regime: "commercial_nsa",
      label: "Commercial / NSA ERISA",
      sla_note: "Subject to No Surprises Act >=90-day verification cycle and 2-business-day update window.",
    };
  }
  return {
    regime: "unclassified_regime",
    label: "Unclassified Regime",
    sla_note: "Confirm line of business before applying commercial NSA deadlines.",
  };
}

export function classifyRegulatoryRegimes(
  networks: string[],
  source?: string | null
): RegulatoryRegimeInfo[] {
  const candidates = networks.filter(Boolean).length ? networks.filter(Boolean) : source ? [source] : [];
  const seen = new Set<string>();
  const out: RegulatoryRegimeInfo[] = [];
  for (const item of candidates) {
    const r = classifyRegulatoryRegime(item);
    if (!seen.has(r.regime)) {
      seen.add(r.regime);
      out.push(r);
    }
  }
  return out.length ? out : [classifyRegulatoryRegime(source)];
}

function digits10(value: string | null | undefined): string | null {
  if (!value) return null;
  let digits = value.split(/[xX]/)[0].replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("1")) digits = digits.slice(1);
  return digits.length === 10 ? digits : null;
}

export function classifyPhoneConflict(
  phoneA: string | null | undefined,
  phoneB: string | null | undefined
): PhoneConflictInfo {
  const pa = digits10(phoneA);
  const pb = digits10(phoneB);
  if (!pa || !pb) {
    return {
      category: "missing_phone",
      label: "Missing Phone Comparison",
      guidance: "One or both sources lack a valid 10-digit US telephone number.",
    };
  }
  if (pa === pb) {
    return {
      category: "exact_match",
      label: "Exact Match",
      guidance: "Normalized 10-digit numbers agree.",
    };
  }
  if (TOLL_FREE_CODES.has(pa.slice(0, 3)) || TOLL_FREE_CODES.has(pb.slice(0, 3))) {
    return {
      category: "toll_free_centralized_line",
      label: "Toll-Free Centralized Desk",
      guidance: "One source lists an 800/8xx call center vs. local office desk; confirm scheduling preference before overwriting.",
    };
  }
  if (pa.slice(0, 6) === pb.slice(0, 6)) {
    return {
      category: "same_npa_nxx_clinic_pbx",
      label: "Same Clinic Prefix (NPA-NXX)",
      guidance: "First 6 digits match, indicating another DID/extension on the same clinic/hospital PBX.",
    };
  }
  if (pa.slice(0, 3) === pb.slice(0, 3)) {
    return {
      category: "same_area_code_different_exchange",
      label: "Same Area Code (Different Exchange)",
      guidance: "Same metro area code with a different exchange; confirm move or off-site scheduling desk.",
    };
  }
  return {
    category: "different_area_code_or_state",
    label: "Different Area Code / State",
    guidance: "Different area code or out-of-state number; high priority for billing/hub check.",
  };
}

export function buildFourGateEvidence(params: {
  npi: string | null | undefined;
  npiLuhnValid: boolean;
  practiceState?: string | null;
  licenseState?: string | null;
  psvVerified?: boolean;
  pecosStatus?: "pecos_ffs_enrolled" | "order_referring_only" | "not_in_medicare_ffs" | "unverified";
  leieClear?: boolean;
  addressConfirmed?: boolean;
  hospitalBasedNewptLeak?: boolean;
  directoryNote?: string;
}): FourGateEvidence {
  const prac = (params.practiceState ?? "TN").trim().toUpperCase();
  const lic = (params.licenseState ?? "").trim().toUpperCase();
  const psv = Boolean(params.psvVerified);

  const gate1 =
    params.npi && params.npiLuhnValid
      ? { status: "active_npi", label: "Valid Luhn NPI", source: "CMS ISO 7812 / NPPES" }
      : {
          status: params.npi ? "invalid_checksum" : "unlinked",
          label: params.npi ? "Invalid NPI Checksum" : "Unlinked Identity",
          source: "CMS ISO 7812",
        };

  let gate2: FourGateEvidence["gate2_licensure"];
  if (psv) {
    gate2 = {
      status: "primary_source_verified",
      label: "Primary-Source Verified (TN Board)",
      psv_required: false,
      note: "Confirmed directly against state licensing board record.",
    };
  } else if (lic && prac && lic !== prac) {
    gate2 = {
      status: "out_of_state_license_only_unverified_psv",
      label: `Out-of-State License (${lic} Only — PSV Required)`,
      psv_required: true,
      note: `Self-reported ${lic} license does not match ${prac} practice site; verify compact (eNLC) or active ${prac} board record.`,
    };
  } else if (lic) {
    gate2 = {
      status: "self_reported_state_match_unverified_psv",
      label: `Self-Reported ${lic} License (PSV Required)`,
      psv_required: true,
      note: "Self-reported NPPES/roster license matches clinic state, but never replaces primary-source board verification.",
    };
  } else {
    gate2 = {
      status: "no_license_state_recorded_unverified_psv",
      label: "No License Recorded (PSV Required)",
      psv_required: true,
      note: "No state license recorded; manual primary-source board verification required.",
    };
  }

  const pStatus = params.pecosStatus ?? "pecos_ffs_enrolled";
  const g3Map: Record<string, { label: string; note: string }> = {
    pecos_ffs_enrolled: {
      label: "PECOS FFS Enrolled",
      note: "Medicare Part B FFS individual/reassignment enrollment verified.",
    },
    order_referring_only: {
      label: "Order & Referring Only",
      note: "Order/Referring eligible without full PECOS Part B billing enrollment.",
    },
    not_in_medicare_ffs: {
      label: "Not in Medicare PECOS",
      note: "Zero Medicare enrollment; check Medicaid/pediatric/dental scope.",
    },
    unverified: {
      label: "PECOS Unchecked",
      note: "LEIE exclusion screen clear; Medicare PECOS enrollment requires reconciliation.",
    },
  };
  const g3Info = g3Map[pStatus] ?? g3Map.unverified;

  const addrOk = params.addressConfirmed ?? true;
  const hbLeak = params.hospitalBasedNewptLeak ?? false;
  return {
    gate1_identity: gate1,
    gate2_licensure: gate2,
    gate3_enrollment: {
      status: pStatus,
      leie_clear: params.leieClear ?? true,
      label: g3Info.label,
      note: g3Info.note,
    },
    gate4_directory: {
      address_confirmed: addrOk,
      hospital_based_newpt_leak: hbLeak,
      label: hbLeak
        ? "Hospital-Based Accepting New Patients"
        : addrOk
          ? "Confirmed Location & Panel"
          : "Address Unconfirmed vs NPD/NPPES",
      note:
        params.directoryNote ??
        (hbLeak
          ? "Hospital-based specialist marked accepting new patients; confirm direct outpatient scheduling."
          : "Location and panel fields aligned with source assertions."),
    },
  };
}
