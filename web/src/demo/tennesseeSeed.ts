import { isValidNpi } from "@/lib/format";
import type {
  CaseActionInput,
  DirectoryRecord,
  ExportPreviewResult,
  FeedVersionDetail,
  IntakeSampleOption,
  IntakeSession,
  ManagedFeedSummary,
  SchemaCatalogStatus,
  SchemaVariantSummary,
  SourceSchemaInspection,
  SourceSchemaPreview,
  WorkCaseDetail,
  WorkCaseSummary,
  WorkbenchOverview,
} from "@/lib/types";

export const SAMPLE_OPTIONS: IntakeSampleOption[] = [
  {
    id: "cumberland-monthly-known",
    title: "Cumberland Monthly Roster",
    subtitle: "Matches reviewed variant cumberland-ehr-roster offline (0 LLM calls).",
    filename: "cumberland-roster-nov-2026.csv",
    source: "cumberland-clinic",
    payer: "volunteer-ppo",
    sourceVersion: "2026-q4",
    profile: "flat",
    badge: "Known Variant · Model Off",
    payloadText: [
      "record_id,npi,provider_name,specialty,location_id,location_name,address,city,state,zip,phone,reference_phone,network_label,Dir_Exclude_Flag,source_updated_at",
      "CVMG-01,1990001012,Dr. Elena Morales MD,207Q00000X Family Medicine,NASH-MAIN,Nashville Midtown Clinic,2100 West End Ave Suite 400,Nashville,TN,37203,6155550142,6155550142,Volunteer Commercial PPO; MidSouth Medicare Advantage,N,2026-11-18",
      "CVMG-06,1990001061,Dr. Rachel Alvarez MD,207V00000X Obstetrics & Gynecology,NASH-MAIN,Nashville Midtown Clinic,2100 West End Ave Suite 400,Nashville,TN,37203,6155550106,,Volunteer Commercial PPO,Y,2026-11-18",
      "CVMG-08,1990001079,Dr. Priya Nair MD,207R00000X Internal Medicine,FRNK-WEST,Franklin Cool Springs Clinic,1550 Mallory Ln Suite 210,Franklin,TN,37067,6155550107,6155550107,Volunteer Commercial PPO,N,2026-11-18",
    ].join("\n"),
  },
  {
    id: "payer-delta-exclusion-trap",
    title: "Renamed Payer Delta (Exclusion Trap)",
    subtitle: "Renamed headers + inverted Dir_Exclude_Flag=Y + 1 invalid Luhn NPI.",
    filename: "midsouth-payer-delta.csv",
    source: "midsouth-payer",
    payer: "midsouth-ma",
    sourceVersion: "2026-11",
    profile: "flat",
    badge: "New Schema · Luhn + Flag Check",
    payloadText: [
      "Member_Record_ID,Clinician_NPI,Full_Name,NUCC_Taxonomy,Clinic_Code,Street_Addr,City,State,Postal_Code,Scheduling_Phone,Dir_Exclude_Flag,Updated_Date",
      "MS-101,1990001012,Dr. Elena Morales MD,207Q00000X Family Medicine,NASH-MAIN,2100 West End Ave Suite 400,Nashville,TN,37203,615-555-0142,N,2026-11-20",
      "MS-102,1990001061,Dr. Rachel Alvarez MD,207V00000X Obstetrics & Gynecology,NASH-MAIN,2100 West End Ave Suite 400,Nashville,TN,37203,615-555-0106,Y,2026-11-20",
      "MS-103,1234567890,Dr. Bad Checksum Example,207R00000X Internal Medicine,FRNK-WEST,1550 Mallory Ln Suite 210,Franklin,TN,37067,615-555-0199,N,2026-11-20",
    ].join("\n"),
  },
  {
    id: "fhir-plannet-bundle",
    title: "Saved FHIR R4 / Plan-Net Bundle",
    subtitle: "Conservative Practitioner, Location, Organization & PractitionerRole graph.",
    filename: "cumberland-plannet-bundle.json",
    source: "midsouth-fhir",
    profile: "fhir-plannet-r4",
    badge: "FHIR R4 · Plan-Net 1.2",
    payloadText: JSON.stringify(
      {
        resourceType: "Bundle",
        type: "searchset",
        entry: [
          {
            fullUrl: "https://example.invalid/fhir/Practitioner/elena-morales",
            resource: {
              resourceType: "Practitioner",
              id: "elena-morales",
              identifier: [{ system: "http://hl7.org/fhir/sid/us-npi", value: "1990001012" }],
              name: [{ text: "Dr. Elena Morales, MD" }],
            },
          },
          {
            fullUrl: "https://example.invalid/fhir/Location/nash-main",
            resource: {
              resourceType: "Location",
              id: "nash-main",
              name: "Nashville Midtown Clinic",
              address: {
                line: ["2100 West End Ave, Suite 400"],
                city: "Nashville",
                state: "TN",
                postalCode: "37203",
              },
              telecom: [{ system: "phone", value: "615-555-0142" }],
            },
          },
          {
            fullUrl: "https://example.invalid/fhir/Organization/volunteer-ppo",
            resource: {
              resourceType: "Organization",
              id: "volunteer-ppo",
              meta: {
                profile: [
                  "http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/plannet-Network|1.2.0",
                ],
              },
              name: "Volunteer Commercial PPO",
            },
          },
          {
            fullUrl: "https://example.invalid/fhir/PractitionerRole/morales-nash",
            resource: {
              resourceType: "PractitionerRole",
              id: "morales-nash",
              practitioner: { reference: "Practitioner/elena-morales" },
              location: [{ reference: "Location/nash-main" }],
              extension: [
                {
                  url: "http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/network-reference",
                  valueReference: { reference: "Organization/volunteer-ppo" },
                },
              ],
            },
          },
        ],
      },
      null,
      2
    ),
  },
];

interface DemoState {
  directory: DirectoryRecord[];
  cases: WorkCaseDetail[];
  variants: SchemaVariantSummary[];
  catalogRevision: number;
  feeds: ManagedFeedSummary[];
  versions: Record<string, FeedVersionDetail>;
  intakes: Record<string, { session: IntakeSession; rawText: string }>;
}

function buildInitialDirectory(): DirectoryRecord[] {
  return [
    {
      id: "1990001012:NASH-MAIN",
      provider_name: "Dr. Elena Morales, MD",
      npi: "1990001012",
      npi_luhn_valid: true,
      specialty: "207Q00000X · Family Medicine",
      location_code: "NASH-MAIN",
      location_name: "Nashville Midtown Clinic",
      address: "2100 West End Ave, Suite 400",
      city: "Nashville",
      state: "TN",
      zip: "37203",
      phone: "6155550101",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO", "MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 1,
      primary_case_id: "case-cvmg-01",
      source: "cumberland-clinic",
    },
    {
      id: "1990001020:FRNK-WEST",
      provider_name: "Dr. Marcus Vance, DO",
      npi: "1990001020",
      npi_luhn_valid: true,
      specialty: "207R00000X · Internal Medicine",
      location_code: "FRNK-WEST",
      location_name: "Franklin Cool Springs Clinic",
      address: "1550 Mallory Ln, Suite 210",
      city: "Franklin",
      state: "TN",
      zip: "37067",
      phone: "6155550102",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 1,
      primary_case_id: "case-cvmg-02",
      source: "cumberland-clinic",
    },
    {
      id: "1990001046:MURF-EAST",
      provider_name: "Dr. Hannah Brooks, MD",
      npi: "1990001046",
      npi_luhn_valid: true,
      specialty: "208000000X · Pediatrics",
      location_code: "MURF-EAST",
      location_name: "Murfreesboro Medical Plaza",
      address: "1725 Medical Center Pkwy, Suite 300",
      city: "Murfreesboro",
      state: "TN",
      zip: "37129",
      phone: "6155550104",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 1,
      primary_case_id: "case-cvmg-04",
      source: "cumberland-clinic",
    },
    {
      id: "1990001053:HEND-LAKE",
      provider_name: "Dr. David Chen, MD",
      npi: "1990001053",
      npi_luhn_valid: true,
      specialty: "207X00000X · Orthopedic Surgery",
      location_code: "HEND-LAKE",
      location_name: "Hendersonville Indian Lake",
      address: "300 Indian Lake Blvd, Suite 150",
      city: "Hendersonville",
      state: "TN",
      zip: "37075",
      phone: "6155550105",
      phone_extension: null,
      networks: ["MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 1,
      primary_case_id: "case-cvmg-05",
      source: "cumberland-clinic",
    },
    {
      id: "1990001061:NASH-MAIN",
      provider_name: "Dr. Rachel Alvarez, MD",
      npi: "1990001061",
      npi_luhn_valid: true,
      specialty: "207V00000X · Obstetrics & Gynecology",
      location_code: "NASH-MAIN",
      location_name: "Nashville Midtown Clinic",
      address: "2100 West End Ave, Suite 400",
      city: "Nashville",
      state: "TN",
      zip: "37203",
      phone: "6155550106",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: false,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 1,
      primary_case_id: "case-cvmg-06",
      source: "cumberland-clinic",
    },
    {
      id: "1990001038:BRNT-PARK",
      provider_name: "Dr. Samuel Okafor, MD",
      npi: "1990001038",
      npi_luhn_valid: true,
      specialty: "207RC0000X · Cardiovascular Disease",
      location_code: "BRNT-PARK",
      location_name: "Brentwood Maryland Farms",
      address: "5120 Maryland Way, Suite 120",
      city: "Brentwood",
      state: "TN",
      zip: "37027",
      phone: "6155550139",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO", "MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-14T16:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001038:NASH-MAIN",
      provider_name: "Dr. Samuel Okafor, MD",
      npi: "1990001038",
      npi_luhn_valid: true,
      specialty: "207RC0000X · Cardiovascular Disease",
      location_code: "NASH-MAIN",
      location_name: "Nashville Midtown Clinic",
      address: "2100 West End Ave, Suite 400",
      city: "Nashville",
      state: "TN",
      zip: "37203",
      phone: "6155550101",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO", "MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001079:FRNK-WEST",
      provider_name: "Dr. Priya Nair, MD",
      npi: "1990001079",
      npi_luhn_valid: true,
      specialty: "207R00000X · Internal Medicine",
      location_code: "FRNK-WEST",
      location_name: "Franklin Cool Springs Clinic",
      address: "1550 Mallory Ln, Suite 210",
      city: "Franklin",
      state: "TN",
      zip: "37067",
      phone: "6155550107",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001079:BRNT-PARK",
      provider_name: "Dr. Priya Nair, MD",
      npi: "1990001079",
      npi_luhn_valid: true,
      specialty: "207R00000X · Internal Medicine",
      location_code: "BRNT-PARK",
      location_name: "Brentwood Maryland Farms",
      address: "5120 Maryland Way, Suite 120",
      city: "Brentwood",
      state: "TN",
      zip: "37027",
      phone: "6155550103",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001087:MURF-EAST",
      provider_name: "Dr. Caleb Wright, MD",
      npi: "1990001087",
      npi_luhn_valid: true,
      specialty: "207Q00000X · Family Medicine",
      location_code: "MURF-EAST",
      location_name: "Murfreesboro Medical Plaza",
      address: "1725 Medical Center Pkwy, Suite 300",
      city: "Murfreesboro",
      state: "TN",
      zip: "37129",
      phone: "6155550108",
      phone_extension: null,
      networks: ["MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001095:HEND-LAKE",
      provider_name: "Naomi Foster, APRN",
      npi: "1990001095",
      npi_luhn_valid: true,
      specialty: "363LF0000X · Family Nurse Practitioner",
      location_code: "HEND-LAKE",
      location_name: "Hendersonville Indian Lake",
      address: "300 Indian Lake Blvd, Suite 150",
      city: "Hendersonville",
      state: "TN",
      zip: "37075",
      phone: "6155550109",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO", "MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001103:NASH-MAIN",
      provider_name: "Dr. Jordan Patel, MD",
      npi: "1990001103",
      npi_luhn_valid: true,
      specialty: "207RC0000X · Cardiovascular Disease",
      location_code: "NASH-MAIN",
      location_name: "Nashville Midtown Clinic",
      address: "2100 West End Ave, Suite 400",
      city: "Nashville",
      state: "TN",
      zip: "37203",
      phone: "6155550110",
      phone_extension: null,
      networks: ["MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001111:MURF-EAST",
      provider_name: "Tessa Gallagher, PA-C",
      npi: "1990001111",
      npi_luhn_valid: true,
      specialty: "363A00000X · Physician Assistant",
      location_code: "MURF-EAST",
      location_name: "Murfreesboro Medical Plaza",
      address: "1725 Medical Center Pkwy, Suite 300",
      city: "Murfreesboro",
      state: "TN",
      zip: "37129",
      phone: "6155550111",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001111:FRNK-WEST",
      provider_name: "Tessa Gallagher, PA-C",
      npi: "1990001111",
      npi_luhn_valid: true,
      specialty: "363A00000X · Physician Assistant",
      location_code: "FRNK-WEST",
      location_name: "Franklin Cool Springs Clinic",
      address: "1550 Mallory Ln, Suite 210",
      city: "Franklin",
      state: "TN",
      zip: "37067",
      phone: "6155550114",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
    {
      id: "1990001129:BRNT-PARK",
      provider_name: "Dr. Owen Reynolds, MD",
      npi: "1990001129",
      npi_luhn_valid: true,
      specialty: "207X00000X · Orthopedic Surgery",
      location_code: "BRNT-PARK",
      location_name: "Brentwood Maryland Farms",
      address: "5120 Maryland Way, Suite 120",
      city: "Brentwood",
      state: "TN",
      zip: "37027",
      phone: "6155550112",
      phone_extension: null,
      networks: ["Volunteer Commercial PPO", "MidSouth Medicare Advantage"],
      directory_visible: true,
      verified_at: "2026-11-02T14:00:00+00:00",
      open_issues: 0,
      primary_case_id: null,
      source: "cumberland-clinic",
    },
  ];
}

function buildInitialCases(): WorkCaseDetail[] {
  return [
    {
      id: "case-cvmg-01",
      kind: "correction",
      provider_name: "Dr. Elena Morales, MD",
      npi: "1990001012",
      location_id: "cumberland-clinic:NASH-MAIN",
      location_code: "NASH-MAIN",
      location_label: "Nashville Midtown Clinic",
      clinic_name: "Nashville Midtown Clinic",
      field_name: "phone",
      issue: "Location phone differs from submitted clinic reference",
      risk_level: "high",
      risk_reason: "Patients dialing published number reach legacy routing; NSA 2-day SLA applies",
      status: "new",
      owner: null,
      follow_up: "2026-11-23",
      version: 0,
      proposal: null,
      observed: null,
      listing_value: "6155550101",
      reference_value: "6155550142",
      source: "cumberland-clinic",
      created_at: "2026-11-16T14:00:00+00:00",
      updated_at: "2026-11-20T09:15:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "6155550101",
        reference_value: "6155550142",
        location_id: "cumberland-clinic:NASH-MAIN",
        locator: "row:2",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001012",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-01",
        normalized: {
          record_id: "CVMG-01",
          npi: "1990001012",
          provider_name: "Dr. Elena Morales, MD",
          specialty: "207Q00000X · Family Medicine",
          location_id: "NASH-MAIN",
          address: "2100 West End Ave, Suite 400",
          city: "Nashville",
          state: "TN",
          zip: "37203",
          phone: "6155550101",
          reference_phone: "6155550142",
        },
        original: {
          record_id: "CVMG-01",
          npi: "1990001012",
          provider_name: "Dr. Elena Morales, MD",
          location_id: "NASH-MAIN",
          phone: "6155550101",
          reference_phone: "6155550142",
          Dir_Exclude_Flag: "N",
        },
      },
      history: [],
    },
    {
      id: "case-cvmg-02",
      kind: "correction",
      provider_name: "Dr. Marcus Vance, DO",
      npi: "1990001020",
      location_id: "cumberland-clinic:FRNK-WEST",
      location_code: "FRNK-WEST",
      location_label: "Franklin Cool Springs Clinic",
      clinic_name: "Franklin Cool Springs Clinic",
      field_name: "phone",
      issue: "Location phone differs from submitted clinic reference",
      risk_level: "high",
      risk_reason: "Patients may be unable to reach Cool Springs Internal Medicine scheduling",
      status: "triaged",
      owner: "M. Brooks",
      follow_up: "2026-11-24",
      version: 3,
      proposal: null,
      observed: null,
      listing_value: "6155550102",
      reference_value: "6155550188",
      source: "cumberland-clinic",
      created_at: "2026-11-12T10:00:00+00:00",
      updated_at: "2026-11-18T15:35:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "6155550102",
        reference_value: "6155550188",
        location_id: "cumberland-clinic:FRNK-WEST",
        locator: "row:3",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001020",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-02",
        normalized: {
          record_id: "CVMG-02",
          npi: "1990001020",
          provider_name: "Dr. Marcus Vance, DO",
          specialty: "207R00000X · Internal Medicine",
          location_id: "FRNK-WEST",
          address: "1550 Mallory Ln, Suite 210",
          city: "Franklin",
          state: "TN",
          zip: "37067",
          phone: "6155550102",
          reference_phone: "6155550188",
        },
        original: {
          record_id: "CVMG-02",
          npi: "1990001020",
          provider_name: "Dr. Marcus Vance, DO",
          location_id: "FRNK-WEST",
          phone: "6155550102",
          reference_phone: "6155550188",
        },
      },
      history: [
        {
          id: 1,
          case_id: "case-cvmg-02",
          action: "assign",
          actor: "M. Brooks",
          reason: "Assign Cool Springs clinic outreach",
          payload: { owner: "M. Brooks", follow_up: "2026-11-24" },
          from_status: "new",
          to_status: "new",
          occurred_at: "2026-11-17T13:00:00+00:00",
        },
        {
          id: 2,
          case_id: "case-cvmg-02",
          action: "outreach",
          actor: "M. Brooks",
          reason: "Called Franklin front desk; line went to voicemail",
          payload: { method: "phone", outcome: "no_answer", contact_target: "Franklin Cool Springs Desk" },
          from_status: "new",
          to_status: "new",
          occurred_at: "2026-11-18T15:30:00+00:00",
        },
        {
          id: 3,
          case_id: "case-cvmg-02",
          action: "triage",
          actor: "M. Brooks",
          reason: "Confirmed mismatch against EHR intake; awaiting callback",
          payload: {},
          from_status: "new",
          to_status: "triaged",
          occurred_at: "2026-11-18T15:35:00+00:00",
        },
      ],
    },
    {
      id: "case-cvmg-04",
      kind: "correction",
      provider_name: "Dr. Hannah Brooks, MD",
      npi: "1990001046",
      location_id: "cumberland-clinic:MURF-EAST",
      location_code: "MURF-EAST",
      location_label: "Murfreesboro Medical Plaza",
      clinic_name: "Murfreesboro Medical Plaza",
      field_name: "phone",
      issue: "Location phone differs from submitted clinic reference",
      risk_level: "high",
      risk_reason: "Submitted to payer under 2-day NSA window; awaiting payer directory confirmation",
      status: "pending_verification",
      owner: "M. Brooks",
      follow_up: "2026-11-24",
      version: 4,
      proposal: "6155550144",
      observed: null,
      listing_value: "6155550104",
      reference_value: "6155550144",
      source: "cumberland-clinic",
      created_at: "2026-11-14T09:00:00+00:00",
      updated_at: "2026-11-19T17:10:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "6155550104",
        reference_value: "6155550144",
        location_id: "cumberland-clinic:MURF-EAST",
        locator: "row:5",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001046",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-04",
        normalized: {
          record_id: "CVMG-04",
          npi: "1990001046",
          provider_name: "Dr. Hannah Brooks, MD",
          specialty: "208000000X · Pediatrics",
          location_id: "MURF-EAST",
          address: "1725 Medical Center Pkwy, Suite 300",
          city: "Murfreesboro",
          state: "TN",
          zip: "37129",
          phone: "6155550104",
          reference_phone: "6155550144",
        },
        original: {
          record_id: "CVMG-04",
          npi: "1990001046",
          provider_name: "Dr. Hannah Brooks, MD",
          location_id: "MURF-EAST",
          phone: "6155550104",
          reference_phone: "6155550144",
        },
      },
      history: [
        {
          id: 1,
          case_id: "case-cvmg-04",
          action: "assign",
          actor: "M. Brooks",
          reason: "Assign Murfreesboro pediatrics correction",
          payload: { owner: "M. Brooks" },
          from_status: "new",
          to_status: "new",
          occurred_at: "2026-11-17T10:00:00+00:00",
        },
        {
          id: 2,
          case_id: "case-cvmg-04",
          action: "triage",
          actor: "M. Brooks",
          reason: "Validated direct scheduling number with clinic desk",
          payload: {},
          from_status: "new",
          to_status: "triaged",
          occurred_at: "2026-11-18T11:00:00+00:00",
        },
        {
          id: 3,
          case_id: "case-cvmg-04",
          action: "approve",
          actor: "Operations Lead",
          reason: "Approve Murfreesboro phone update",
          payload: { proposal: "6155550144" },
          from_status: "triaged",
          to_status: "approved",
          occurred_at: "2026-11-19T14:20:00+00:00",
        },
        {
          id: 4,
          case_id: "case-cvmg-04",
          action: "submit",
          actor: "Operations Lead",
          reason: "Submitted under NSA 2-day SLA window",
          payload: { submission_reference: "VOL-2026-1119-MURF" },
          from_status: "approved",
          to_status: "pending_verification",
          occurred_at: "2026-11-19T17:10:00+00:00",
        },
      ],
    },
    {
      id: "case-cvmg-05",
      kind: "qa",
      provider_name: "Dr. David Chen, MD",
      npi: "1990001053",
      location_id: "cumberland-clinic:HEND-LAKE",
      location_code: "HEND-LAKE",
      location_label: "Hendersonville Indian Lake",
      clinic_name: "Hendersonville Indian Lake",
      field_name: "address",
      issue: "Suite mismatch between clinic EHR (Suite 150) and NPPES (Suite 155)",
      risk_level: "medium",
      risk_reason: "Address discrepancy affects patient wayfinding and mail delivery",
      status: "needs_information",
      owner: "M. Brooks",
      follow_up: "2026-11-25",
      version: 1,
      proposal: null,
      observed: null,
      listing_value: "300 Indian Lake Blvd, Suite 150",
      reference_value: "300 Indian Lake Blvd, Suite 155",
      source: "cumberland-clinic",
      created_at: "2026-11-15T11:00:00+00:00",
      updated_at: "2026-11-19T09:40:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "300 Indian Lake Blvd, Suite 150",
        reference_value: "300 Indian Lake Blvd, Suite 155",
        location_id: "cumberland-clinic:HEND-LAKE",
        locator: "row:6",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001053",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-05",
        normalized: {
          record_id: "CVMG-05",
          npi: "1990001053",
          provider_name: "Dr. David Chen, MD",
          specialty: "207X00000X · Orthopedic Surgery",
          location_id: "HEND-LAKE",
          address: "300 Indian Lake Blvd, Suite 150",
          city: "Hendersonville",
          state: "TN",
          zip: "37075",
          phone: "6155550105",
        },
        original: {
          record_id: "CVMG-05",
          npi: "1990001053",
          provider_name: "Dr. David Chen, MD",
          location_id: "HEND-LAKE",
          address: "300 Indian Lake Blvd, Suite 150",
        },
      },
      history: [
        {
          id: 1,
          case_id: "case-cvmg-05",
          action: "needs_information",
          actor: "M. Brooks",
          reason: "NPPES shows Suite 155 while clinic EHR lists Suite 150; requested lease confirmation",
          payload: {},
          from_status: "new",
          to_status: "needs_information",
          occurred_at: "2026-11-19T09:40:00+00:00",
        },
      ],
    },
    {
      id: "case-cvmg-06",
      kind: "qa",
      provider_name: "Dr. Rachel Alvarez, MD",
      npi: "1990001061",
      location_id: "cumberland-clinic:NASH-MAIN",
      location_code: "NASH-MAIN",
      location_label: "Nashville Midtown Clinic",
      clinic_name: "Nashville Midtown Clinic",
      field_name: "directory_visible",
      issue: "Confirm directory suppression flag (Dir_Exclude_Flag = Y)",
      risk_level: "medium",
      risk_reason: "Suppression hides clinician from public search without terminating participation",
      status: "new",
      owner: null,
      follow_up: null,
      version: 0,
      proposal: null,
      observed: null,
      listing_value: "Listed (true)",
      reference_value: "Excluded (false · Dir_Exclude_Flag=Y)",
      source: "cumberland-clinic",
      created_at: "2026-11-16T14:00:00+00:00",
      updated_at: "2026-11-16T14:00:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "Listed (true)",
        reference_value: "Excluded (false)",
        location_id: "cumberland-clinic:NASH-MAIN",
        locator: "row:7",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001061",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-06",
        normalized: {
          record_id: "CVMG-06",
          npi: "1990001061",
          provider_name: "Dr. Rachel Alvarez, MD",
          specialty: "207V00000X · Obstetrics & Gynecology",
          location_id: "NASH-MAIN",
          directory_visible: false,
          phone: "6155550106",
        },
        original: {
          record_id: "CVMG-06",
          npi: "1990001061",
          provider_name: "Dr. Rachel Alvarez, MD",
          location_id: "NASH-MAIN",
          Dir_Exclude_Flag: "Y",
        },
      },
      history: [],
    },
    {
      id: "case-cvmg-03",
      kind: "correction",
      provider_name: "Dr. Samuel Okafor, MD",
      npi: "1990001038",
      location_id: "cumberland-clinic:BRNT-PARK",
      location_code: "BRNT-PARK",
      location_label: "Brentwood Maryland Farms",
      clinic_name: "Brentwood Maryland Farms",
      field_name: "phone",
      issue: "Location phone differs from submitted clinic reference",
      risk_level: "high",
      risk_reason: "Verified updated cardiology scheduling line in payer directory",
      status: "verified",
      owner: "M. Brooks",
      follow_up: null,
      version: 6,
      proposal: "6155550139",
      observed: "6155550139",
      listing_value: "6155550103",
      reference_value: "6155550139",
      source: "cumberland-clinic",
      created_at: "2026-11-05T10:00:00+00:00",
      updated_at: "2026-11-14T16:00:00+00:00",
      evidence: {
        designation: "synthetic",
        listing_value: "6155550103",
        reference_value: "6155550139",
        location_id: "cumberland-clinic:BRNT-PARK",
        locator: "row:4",
        source: "cumberland-clinic",
        provider_id: "NPI:1990001038",
        receipt_id: "rcpt-v1",
        observation_id: "obs-cvmg-03",
        normalized: {
          record_id: "CVMG-03",
          npi: "1990001038",
          provider_name: "Dr. Samuel Okafor, MD",
          specialty: "207RC0000X · Cardiovascular Disease",
          location_id: "BRNT-PARK",
          address: "5120 Maryland Way, Suite 120",
          city: "Brentwood",
          state: "TN",
          zip: "37027",
          phone: "6155550103",
          reference_phone: "6155550139",
        },
        original: {
          record_id: "CVMG-03",
          npi: "1990001038",
          provider_name: "Dr. Samuel Okafor, MD",
          location_id: "BRNT-PARK",
          phone: "6155550103",
          reference_phone: "6155550139",
        },
      },
      history: [
        {
          id: 1,
          case_id: "case-cvmg-03",
          action: "assign",
          actor: "M. Brooks",
          reason: "Assign Brentwood cardiology verification",
          payload: { owner: "M. Brooks" },
          from_status: "new",
          to_status: "new",
          occurred_at: "2026-11-08T10:00:00+00:00",
        },
        {
          id: 2,
          case_id: "case-cvmg-03",
          action: "outreach",
          actor: "M. Brooks",
          reason: "Practice manager confirmed updated scheduling line",
          payload: {
            method: "phone",
            outcome: "response_received",
            reported_phone: "6155550139",
            contact_target: "Brentwood Practice Manager",
          },
          from_status: "new",
          to_status: "new",
          occurred_at: "2026-11-10T16:15:00+00:00",
        },
        {
          id: 3,
          case_id: "case-cvmg-03",
          action: "triage",
          actor: "M. Brooks",
          reason: "Evidence complete from office manager",
          payload: {},
          from_status: "new",
          to_status: "triaged",
          occurred_at: "2026-11-10T16:20:00+00:00",
        },
        {
          id: 4,
          case_id: "case-cvmg-03",
          action: "approve",
          actor: "Operations Lead",
          reason: "Approve verified Brentwood phone correction",
          payload: { proposal: "6155550139" },
          from_status: "triaged",
          to_status: "approved",
          occurred_at: "2026-11-11T09:00:00+00:00",
        },
        {
          id: 5,
          case_id: "case-cvmg-03",
          action: "submit",
          actor: "Operations Lead",
          reason: "Submitted to Volunteer PPO roster portal",
          payload: { submission_reference: "VOL-2026-1111-BRNT" },
          from_status: "approved",
          to_status: "pending_verification",
          occurred_at: "2026-11-11T09:15:00+00:00",
        },
        {
          id: 6,
          case_id: "case-cvmg-03",
          action: "verify",
          actor: "Operations Lead",
          reason: "Observed updated phone in payer directory extract",
          payload: { observed: "6155550139", verification_note: "Verified on Nov 14 payer extract" },
          from_status: "pending_verification",
          to_status: "verified",
          occurred_at: "2026-11-14T16:00:00+00:00",
        },
      ],
    },
  ];
}

function buildInitialState(): DemoState {
  const directory = buildInitialDirectory();
  const initialVariant: SchemaVariantSummary = {
    id: "var-cumberland-ehr-2026q4",
    source: "cumberland-clinic",
    payer: "volunteer-ppo",
    network: null,
    source_version: "2026-q4",
    contract: "payer-network-roster/1",
    grain: "practitioner_office",
    headers: [
      "record_id",
      "npi",
      "provider_name",
      "specialty",
      "location_id",
      "location_name",
      "address",
      "city",
      "state",
      "zip",
      "phone",
      "reference_phone",
      "network_label",
      "Dir_Exclude_Flag",
      "source_updated_at",
    ],
    mapping: {
      record_id: "record_id",
      practitioner_npi: "npi",
      provider_name: "provider_name",
      specialty: "specialty",
      location_id: "location_id",
      address: "address",
      city: "city",
      state: "state",
      zip: "zip",
      phone: "phone",
      directory_visible: "Dir_Exclude_Flag",
      source_updated_at: "source_updated_at",
    },
    transforms: {
      phone: [{ op: "phone_us" }],
      zip: [{ op: "zip_us" }],
      state: [{ op: "state_us" }],
      directory_visible: [{ op: "value_map", values: { Y: false, N: true } }],
      source_updated_at: [{ op: "date", format: "%Y-%m-%d" }],
    },
    source_notes: {
      "cumberland-ehr-guide-2026q4":
        "Cumberland EHR export guide 2026-q4: Dir_Exclude_Flag=Y suppresses public directory visibility without ending network participation.",
    },
  };

  const v1Rows = directory.map((item, idx) => ({
    locator: `row:${idx + 2}`,
    original: {
      record_id: `CVMG-${String(idx + 1).padStart(2, "0")}`,
      npi: item.npi,
      provider_name: item.provider_name,
      location_id: item.location_code,
      location_name: item.location_name,
      phone: item.phone,
      Dir_Exclude_Flag: item.directory_visible ? "N" : "Y",
    },
    normalized: {
      record_id: `CVMG-${String(idx + 1).padStart(2, "0")}`,
      npi: item.npi,
      provider_name: item.provider_name,
      location_id: item.location_code,
      address: item.address,
      city: item.city,
      state: item.state,
      zip: item.zip,
      phone: item.phone,
    },
    problems: [],
    comparison: "new",
  }));

  const v2Rows = directory
    .filter((item) => item.location_code !== "FRNK-WEST")
    .map((item, idx) => ({
      locator: `row:${idx + 2}`,
      original: {
        record_id: `CVMG-${String(idx + 1).padStart(2, "0")}`,
        npi: item.npi,
        provider_name: item.provider_name,
        location_id: item.location_code,
        phone: item.npi === "1990001012" ? "6155550142" : item.phone,
      },
      normalized: {
        record_id: `CVMG-${String(idx + 1).padStart(2, "0")}`,
        npi: item.npi,
        provider_name: item.provider_name,
        location_id: item.location_code,
        address: item.address,
        city: item.city,
        state: item.state,
        zip: item.zip,
        phone: item.npi === "1990001012" ? "6155550142" : item.phone,
      },
      problems: [] as string[],
      comparison: item.npi === "1990001012" ? "changed" : "unchanged",
    }));

  v2Rows.push({
    locator: "row:14",
    original: {
      record_id: "CVMG-ERR-99",
      npi: "199000199",
      provider_name: "Dr. Malformed Roster Entry",
      location_id: "NASH-MAIN",
      phone: "615-55",
    },
    normalized: {
      record_id: "CVMG-ERR-99",
      npi: "199000199",
      provider_name: "Dr. Malformed Roster Entry",
      location_id: "NASH-MAIN",
      address: "2100 West End Ave, Suite 400",
      city: "Nashville",
      state: "TN",
      zip: "37203",
      phone: "61555",
    },
    problems: ["NPI must contain ten digits", "Phone must contain ten digits"],
    comparison: "new",
  });

  const feedId = "feed-cumberland-monthly";
  const v1Id = "ver-2026-11-02";
  const v2Id = "ver-2026-11-16";

  return {
    directory,
    cases: buildInitialCases(),
    variants: [initialVariant],
    catalogRevision: 1,
    feeds: [
      {
        id: feedId,
        name: "Cumberland Valley Monthly Roster",
        source: "cumberland-clinic",
        scope: "weekly-tn-roster",
        current_version: v1Id,
        config: {
          owner: "M. Brooks (TN Ops)",
          enabled: true,
          start_date: "2026-11-02",
        },
        versions: [
          {
            id: v2Id,
            created_at: "2026-11-16T14:00:00+00:00",
            state: "candidate",
            delivery_id: "cumberland-2026-11-16",
            period: "2026-11-16",
            kind: "source_delivery",
          },
          {
            id: v1Id,
            created_at: "2026-11-02T14:00:00+00:00",
            state: "approved",
            delivery_id: "cumberland-2026-11-02",
            period: "2026-11-02",
            kind: "source_delivery",
          },
        ],
      },
    ],
    versions: {
      [v1Id]: {
        id: v1Id,
        feed_id: feedId,
        state: "approved",
        current_version: v1Id,
        created_at: "2026-11-02T14:00:00+00:00",
        row_count: v1Rows.length,
        delivery: {
          delivery_id: "cumberland-2026-11-02",
          period: "2026-11-02",
          as_of: "2026-11-02",
          filename: "cumberland-2026-11-02.csv",
        },
        decision: {
          decision: "approved",
          actor: "Operations Lead",
          reason: "All 15 baseline Cumberland listings verified across 5 Middle TN clinics",
          created_at: "2026-11-02T14:15:00+00:00",
        },
        review: [],
        report_hash: "hash-v1-baseline",
        report: {
          counts: { raw: 15, valid: 15, quarantined: 0, unique: 15 },
          findings: [
            {
              code: "first_version",
              severity: "warning",
              message: "Initial approved baseline; subsequent deliveries compare against this snapshot.",
            },
          ],
          comparison: {
            counts: { new: 15, changed: 0, unchanged: 0, unresolved: 0 },
            missing_from_this_delivery: 0,
          },
        },
        rows: v1Rows,
      },
      [v2Id]: {
        id: v2Id,
        feed_id: feedId,
        state: "candidate",
        current_version: v1Id,
        created_at: "2026-11-16T14:00:00+00:00",
        row_count: v2Rows.length,
        delivery: {
          delivery_id: "cumberland-2026-11-16",
          period: "2026-11-16",
          as_of: "2026-11-16",
          filename: "cumberland-2026-11-16.csv",
        },
        decision: null,
        review: [],
        report_hash: "hash-v2-candidate",
        report: {
          counts: { raw: 13, valid: 12, quarantined: 1, unique: 12 },
          findings: [
            {
              code: "missing_keys",
              severity: "hold",
              message:
                "3 listings from Franklin Cool Springs Clinic (FRNK-WEST) are missing from this delivery; held so active clinic offices are not silently dropped.",
            },
            {
              code: "row_count_drift",
              severity: "hold",
              message: "Raw row count changed by 13.3% relative to approved baseline v1.",
            },
            {
              code: "quarantine",
              severity: "hold",
              message: "1 malformed row (CVMG-ERR-99 at row:14) quarantined with invalid NPI and phone.",
            },
          ],
          comparison: {
            counts: { new: 0, changed: 1, unchanged: 11, unresolved: 0 },
            missing_from_this_delivery: 3,
          },
        },
        rows: v2Rows,
      },
    },
    intakes: {},
  };
}

let state: DemoState = buildInitialState();

export function resetDemoState(): void {
  state = buildInitialState();
}

function parseCsvLines(text: string): { headers: string[]; rows: Array<Record<string, string>> } {
  const lines = text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length > 0);
  if (!lines.length) return { headers: [], rows: [] };
  const splitCsv = (line: string): string[] => {
    const out: string[] = [];
    let current = "";
    let quoted = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '"') {
        quoted = !quoted;
      } else if (ch === "," && !quoted) {
        out.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
    out.push(current.trim());
    return out;
  };
  const headers = splitCsv(lines[0]);
  const rows = lines.slice(1).map((line) => {
    const cells = splitCsv(line);
    const obj: Record<string, string> = {};
    headers.forEach((h, i) => {
      obj[h] = cells[i] ?? "";
    });
    return obj;
  });
  return { headers, rows };
}

function inferDraftMapping(headers: string[]): Record<string, string> {
  const aliases: Record<string, string[]> = {
    record_id: ["record_id", "member_record_id", "roster_key"],
    practitioner_npi: ["npi", "practitioner_npi", "clinician_npi", "clinician npi"],
    provider_name: ["provider_name", "full_name", "clinician_name", "provider name"],
    specialty: ["specialty", "nucc_taxonomy", "taxonomy"],
    location_id: ["location_id", "clinic_code", "office_id", "site_key"],
    address: ["address", "street_addr", "street", "office_address"],
    city: ["city", "town"],
    state: ["state", "region"],
    zip: ["zip", "postal_code", "postal"],
    phone: ["phone", "scheduling_phone", "office_phone", "listed_phone"],
    directory_visible: ["dir_exclude_flag", "directory_flag", "exclude_flag", "directory_visible"],
    source_updated_at: ["source_updated_at", "updated_date", "as_of"],
  };
  const mapping: Record<string, string> = {};
  for (const [target, candidates] of Object.entries(aliases)) {
    const match = headers.find((h) => candidates.includes(h.toLowerCase()));
    if (match) mapping[target] = match;
  }
  return mapping;
}

export const demoClient = {
  async overview(): Promise<WorkbenchOverview> {
    const openCases = state.cases.filter(
      (c) => !["verified", "resolved", "deferred"].includes(c.status)
    );
    const highRisk = openCases.filter((c) => c.risk_level === "high");
    const clean = state.directory.filter((d) => d.open_issues === 0).length;
    const heldCount = state.feeds.reduce(
      (acc, f) => acc + f.versions.filter((v) => v.state === "candidate").length,
      0
    );
    const quarantined = Object.values(state.versions)
      .filter((v) => v.state === "candidate")
      .reduce((acc, v) => acc + Number(v.report.counts.quarantined ?? 0), 0);
    return {
      total_providers: new Set(state.directory.map((d) => d.npi)).size,
      total_locations: new Set(state.directory.map((d) => d.location_code)).size,
      total_directory_listings: state.directory.length,
      clean_rate_pct: state.directory.length
        ? Math.round((1000 * clean) / state.directory.length) / 10
        : 100,
      open_discrepancies: openCases.length,
      high_risk_discrepancies: highRisk.length,
      held_deliveries: heldCount,
      approved_feeds: state.feeds.filter((f) => f.current_version).length,
      sla_at_risk: highRisk.length,
      quarantined_rows: quarantined,
      schema_variants_count: state.variants.length,
      mode: "demo",
      generated_at: new Date().toISOString(),
    };
  },

  async directory(filters?: {
    search?: string;
    location?: string;
    network?: string;
  }): Promise<DirectoryRecord[]> {
    const q = (filters?.search ?? "").trim().toLowerCase();
    return state.directory
      .filter((item) => {
        if (
          q &&
          !(
            item.provider_name.toLowerCase().includes(q) ||
            item.npi.includes(q) ||
            item.specialty.toLowerCase().includes(q) ||
            item.location_name.toLowerCase().includes(q) ||
            item.city.toLowerCase().includes(q)
          )
        ) {
          return false;
        }
        if (filters?.location && item.location_code !== filters.location) return false;
        if (filters?.network && !item.networks.includes(filters.network)) return false;
        return true;
      })
      .sort((a, b) => Number(b.open_issues > 0) - Number(a.open_issues > 0));
  },

  async schemaCatalog(): Promise<SchemaCatalogStatus> {
    return {
      enabled: true,
      catalog_revision: state.catalogRevision,
      variants: [...state.variants],
    };
  },

  async workQueue(): Promise<WorkCaseSummary[]> {
    return state.cases.map(({ evidence: _e, history: _h, ...summary }) => summary);
  },

  async caseDetail(caseId: string): Promise<WorkCaseDetail> {
    const found = state.cases.find((c) => c.id === caseId);
    if (!found) throw new Error("Work case not found");
    return structuredClone(found);
  },

  async recordCaseEvent(caseId: string, payload: CaseActionInput): Promise<WorkCaseDetail> {
    const idx = state.cases.findIndex((c) => c.id === caseId);
    if (idx < 0) throw new Error("Work case not found");
    const current = state.cases[idx];
    if (payload.expected_version !== current.version) {
      throw new Error("Case changed since opened. Refresh and retry.");
    }
    const nextStatusMap: Record<string, string> = {
      triage: "triaged",
      approve: "approved",
      submit: "pending_verification",
      verify: "verified",
      needs_information: "needs_information",
      defer: "deferred",
      resolve: "resolved",
    };
    const nextStatus = nextStatusMap[payload.action] ?? current.status;
    const nowIso = new Date().toISOString();
    const updated: WorkCaseDetail = {
      ...current,
      status: nextStatus,
      owner: payload.owner ?? current.owner,
      follow_up: payload.follow_up ?? current.follow_up,
      proposal: payload.proposal ?? current.proposal,
      observed: payload.observed ?? current.observed,
      version: current.version + 1,
      updated_at: nowIso,
      history: [
        ...current.history,
        {
          id: current.history.length + 1,
          case_id: caseId,
          action: payload.action,
          actor: payload.actor,
          reason: payload.reason,
          payload: { ...payload },
          from_status: current.status,
          to_status: nextStatus,
          occurred_at: nowIso,
        },
      ],
    };
    state.cases[idx] = updated;
    if (["verified", "resolved", "deferred"].includes(nextStatus)) {
      state.directory = state.directory.map((d) =>
        d.primary_case_id === caseId
          ? {
              ...d,
              open_issues: 0,
              primary_case_id: null,
              phone: payload.observed ? payload.observed.replace(/\D/g, "") : d.phone,
              verified_at: nextStatus === "verified" ? nowIso : d.verified_at,
            }
          : d
      );
    }
    return structuredClone(updated);
  },

  async uploadAndInspectIntake(params: {
    filename: string;
    payloadText: string;
    source: string;
    profile: "flat" | "fhir-plannet-r4";
    payer?: string;
    sourceVersion?: string;
  }): Promise<IntakeSession> {
    const receiptId = `demo-rcpt-${Date.now()}`;
    const attemptId = `demo-att-${Date.now()}`;

    if (params.profile === "fhir-plannet-r4") {
      const bundle = JSON.parse(params.payloadText) as {
        entry?: Array<{ resource?: Record<string, unknown> }>;
      };
      const entries = bundle.entry ?? [];
      const rows = entries.map((entry, idx) => ({
        locator: `$.entry[${idx}].resource`,
        original: entry.resource ?? {},
        normalized: {
          resourceType: entry.resource?.resourceType ?? "Unknown",
          id: entry.resource?.id ?? "",
        },
        problems: [],
      }));
      const session: IntakeSession = {
        receipt_id: receiptId,
        attempt_id: attemptId,
        filename: params.filename,
        source: params.source,
        profile: "fhir-plannet-r4",
        state: "preview_ready",
        payer: params.payer ?? null,
        source_version: params.sourceVersion ?? null,
        schema_inspection: null,
        schema_preview: null,
        host_preview: {
          headers: ["resourceType", "id"],
          total: rows.length,
          valid_count: rows.length,
          quarantined_count: 0,
          rows,
        },
      };
      state.intakes[receiptId] = { session, rawText: params.payloadText };
      return structuredClone(session);
    }

    const { headers, rows } = parseCsvLines(params.payloadText);
    const matchingVariant = state.variants.find(
      (v) =>
        v.source === params.source &&
        (v.payer ?? null) === (params.payer ?? null) &&
        (v.source_version ?? null) === (params.sourceVersion ?? null) &&
        headers.every((h) => v.headers.includes(h))
    );

    const mapping = matchingVariant ? matchingVariant.mapping : inferDraftMapping(headers);
    const exclusionCol = Object.entries(mapping).find(([k]) => k === "directory_visible")?.[1];
    const hasExclusionCol = Boolean(exclusionCol && /exclud|flag/i.test(exclusionCol));
    const transforms: Record<string, unknown[]> = matchingVariant
      ? matchingVariant.transforms
      : {
          ...(mapping.phone ? { phone: [{ op: "phone_us" }] } : {}),
          ...(mapping.zip ? { zip: [{ op: "zip_us" }] } : {}),
          ...(mapping.state ? { state: [{ op: "state_us" }] } : {}),
          ...(mapping.directory_visible && hasExclusionCol
            ? { directory_visible: [{ op: "value_map", values: { Y: false, N: true } }] }
            : {}),
        };

    const draft: Record<string, unknown> = matchingVariant
      ? { ...matchingVariant }
      : {
          version: 1,
          source: params.source,
          payer: params.payer ?? null,
          network: null,
          source_version: params.sourceVersion ?? null,
          contract: "payer-network-roster/1",
          grain: "practitioner_office",
          headers,
          mapping,
          transforms,
          ignored_fields: headers.filter((h) => !Object.values(mapping).includes(h)),
          evidence_refs: ["operator-review-note"],
          source_notes: {
            "operator-review-note": hasExclusionCol
              ? `${exclusionCol}=Y suppresses public directory visibility without ending network participation.`
              : "Operator-reviewed header mapping.",
          },
        };

    const schemaInspection: SourceSchemaInspection = {
      inspection: {
        context: {
          source: params.source,
          delivery_id: receiptId,
          payer: params.payer ?? null,
          network: null,
          completeness: "unknown",
          source_version: params.sourceVersion ?? null,
        },
        artifact_sha256: `demo-${receiptId}`,
        format: "csv",
        fields: headers,
        row_count: rows.length,
        signature: `sig-${headers.join("|")}`,
      },
      recognition: {
        status: matchingVariant ? "exact" : "unknown",
        selected_id: matchingVariant ? matchingVariant.id : null,
        candidates: matchingVariant
          ? [{ variant_id: matchingVariant.id, match: "exact" }]
          : [],
        catalog_revision: state.catalogRevision,
      },
      draft,
      variants: matchingVariant ? [{ id: matchingVariant.id, definition: matchingVariant }] : [],
      catalog_revision: state.catalogRevision,
      fields: Object.keys(mapping),
      host_attempt: attemptId,
      notice: "Reviewing a source format does not accept this delivery or change an approved dataset.",
    };

    const session: IntakeSession = {
      receipt_id: receiptId,
      attempt_id: attemptId,
      filename: params.filename,
      source: params.source,
      profile: "flat",
      state: matchingVariant ? "preview_ready" : "needs_mapping",
      payer: params.payer ?? null,
      source_version: params.sourceVersion ?? null,
      schema_inspection: schemaInspection,
      schema_preview: null,
      host_preview: {
        headers,
        total: rows.length,
        valid_count: 0,
        quarantined_count: 0,
        rows: [],
      },
    };

    state.intakes[receiptId] = { session, rawText: params.payloadText };
    const preview = await this.previewSourceSchema(receiptId, draft);
    session.schema_preview = preview;
    return structuredClone(session);
  },

  async previewSourceSchema(
    receiptId: string,
    definition: Record<string, unknown>
  ): Promise<SourceSchemaPreview> {
    const entry = state.intakes[receiptId];
    if (!entry) throw new Error("Receipt not found");
    const { rows } = parseCsvLines(entry.rawText);
    const mapping = (definition.mapping ?? {}) as Record<string, string>;
    const transforms = (definition.transforms ?? {}) as Record<string, Array<{ op: string; values?: Record<string, boolean> }>>;
    const findings: SourceSchemaPreview["report"]["findings"]["items"] = [];
    const counts: Record<string, number> = {};
    const hostRows: IntakeSession["host_preview"]["rows"] = [];

    const normalizedRows = rows.map((raw, idx) => {
      const locator = `$.records[${idx}]`;
      const normalized: Record<string, unknown> = {};
      const problems: string[] = [];
      for (const [target, sourceCol] of Object.entries(mapping)) {
        let val: unknown = raw[sourceCol] ?? "";
        if (target === "phone" && typeof val === "string") {
          const digits = val.replace(/\D/g, "");
          val = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
        }
        if (target === "directory_visible" && typeof val === "string") {
          const vm = transforms.directory_visible?.find((t) => t.op === "value_map")?.values;
          if (vm && val in vm) {
            val = vm[val];
          }
        }
        normalized[target] = val;
      }
      const npi = String(normalized.practitioner_npi ?? normalized.npi ?? "");
      if (npi && !isValidNpi(npi)) {
        const msg = `practitioner_npi ${npi} fails CMS Luhn check-digit validation`;
        problems.push(msg);
        counts.invalid_npi_checksum = (counts.invalid_npi_checksum ?? 0) + 1;
        findings.push({
          code: "invalid_npi_checksum",
          layer: "structure",
          locator,
          message: msg,
          severity: "error",
        });
      }
      const phone = String(normalized.phone ?? "");
      if (phone && phone.replace(/\D/g, "").length !== 10) {
        const msg = "Phone must contain ten digits";
        problems.push(msg);
        counts.invalid_phone = (counts.invalid_phone ?? 0) + 1;
        findings.push({ code: "invalid_phone", layer: "structure", locator, message: msg, severity: "error" });
      }
      hostRows.push({
        locator: `row:${idx + 2}`,
        original: raw,
        normalized: {
          ...normalized,
          npi,
        },
        problems,
      });
      return { locator, normalized };
    });

    entry.session.host_preview = {
      headers: entry.session.host_preview.headers,
      total: hostRows.length,
      valid_count: hostRows.filter((r) => r.problems.length === 0).length,
      quarantined_count: hostRows.filter((r) => r.problems.length > 0).length,
      rows: hostRows,
    };

    const preview: SourceSchemaPreview = {
      preview_token: `tok-${Date.now()}`,
      host_attempt: entry.session.attempt_id,
      catalog_revision: state.catalogRevision,
      report: {
        variant_id:
          entry.session.schema_inspection?.recognition.selected_id ?? "draft-unreviewed",
        row_count: rows.length,
        coverage: "complete_for_declared_scope",
        uninterpreted_fields: [],
        eligibility: {
          policy: "participation_export/1",
          state: findings.length > 0 ? "held" : "eligible_for_host_review",
          reasons: findings.length > 0 ? Object.keys(counts) : [],
          approved: false,
        },
        findings: {
          total: findings.length,
          counts,
          items: findings,
        },
        rows: normalizedRows,
      },
    };
    entry.session.schema_preview = preview;
    return structuredClone(preview);
  },

  async saveAndReviewVariant(params: {
    receiptId: string;
    definition: Record<string, unknown>;
    actor: string;
    reason: string;
  }): Promise<SchemaVariantSummary> {
    const entry = state.intakes[params.receiptId];
    if (!entry) throw new Error("Receipt not found");
    const variantId = `var-${entry.session.source}-${state.variants.length + 1}`;
    const saved: SchemaVariantSummary = {
      id: variantId,
      source: String(params.definition.source ?? entry.session.source),
      payer: (params.definition.payer as string | null) ?? entry.session.payer,
      network: (params.definition.network as string | null) ?? null,
      source_version:
        (params.definition.source_version as string | null) ?? entry.session.source_version,
      contract: "payer-network-roster/1",
      grain: String(params.definition.grain ?? "practitioner_office"),
      headers: (params.definition.headers as string[]) ?? [],
      mapping: (params.definition.mapping as Record<string, string>) ?? {},
      transforms: (params.definition.transforms as Record<string, unknown[]>) ?? {},
      source_notes: (params.definition.source_notes as Record<string, string>) ?? {
        review: params.reason,
      },
    };
    state.variants = [saved, ...state.variants.filter((v) => v.id !== saved.id)];
    state.catalogRevision += 1;
    if (entry.session.schema_inspection) {
      entry.session.schema_inspection.recognition.status = "exact";
      entry.session.schema_inspection.recognition.selected_id = saved.id;
      entry.session.schema_inspection.catalog_revision = state.catalogRevision;
    }
    return structuredClone(saved);
  },

  async acceptIntake(params: {
    receiptId: string;
    actor: string;
    reason: string;
  }): Promise<{ committed: number; quarantined: number }> {
    const entry = state.intakes[params.receiptId];
    if (!entry) throw new Error("Receipt not found");
    entry.session.state = "committed";
    const valid = entry.session.host_preview.valid_count;
    const quarantined = entry.session.host_preview.quarantined_count;
    return { committed: valid, quarantined };
  },

  async feeds(): Promise<ManagedFeedSummary[]> {
    return structuredClone(state.feeds);
  },

  async feedVersion(versionId: string): Promise<FeedVersionDetail> {
    const found = state.versions[versionId];
    if (!found) throw new Error("Dataset version not found");
    return structuredClone(found);
  },

  async acknowledgeHold(params: {
    versionId: string;
    code: string;
    expectedReport: string;
    actor: string;
    reason: string;
  }): Promise<FeedVersionDetail> {
    const version = state.versions[params.versionId];
    if (!version) throw new Error("Dataset version not found");
    version.review.push({
      code: params.code,
      disposition: "acknowledged",
      actor: params.actor,
      reason: params.reason,
      created_at: new Date().toISOString(),
    });
    return structuredClone(version);
  },

  async decideFeedVersion(params: {
    versionId: string;
    decision: "approved" | "rejected";
    expectedReport: string;
    expectedCurrent: string | null;
    actor: string;
    reason: string;
  }): Promise<FeedVersionDetail> {
    const version = state.versions[params.versionId];
    if (!version) throw new Error("Dataset version not found");
    const holds = version.report.findings.filter((f) => f.severity === "hold").map((f) => f.code);
    const acked = new Set(version.review.filter((r) => r.disposition === "acknowledged").map((r) => r.code));
    if (params.decision === "approved" && holds.some((code) => !acked.has(code))) {
      throw new Error("Acknowledge all soft quality holds before approving this version");
    }
    version.state = params.decision;
    version.decision = {
      decision: params.decision,
      actor: params.actor,
      reason: params.reason,
      created_at: new Date().toISOString(),
    };
    if (params.decision === "approved") {
      state.feeds = state.feeds.map((f) =>
        f.id === version.feed_id
          ? {
              ...f,
              current_version: version.id,
              versions: f.versions.map((v) =>
                v.id === version.id ? { ...v, state: "approved" } : v
              ),
            }
          : f
      );
      version.current_version = version.id;
    } else {
      state.feeds = state.feeds.map((f) =>
        f.id === version.feed_id
          ? {
              ...f,
              versions: f.versions.map((v) =>
                v.id === version.id ? { ...v, state: "rejected" } : v
              ),
            }
          : f
      );
    }
    return structuredClone(version);
  },

  async previewFeedExport(
    versionId: string,
    locationId?: string | null
  ): Promise<ExportPreviewResult> {
    const version = state.versions[versionId];
    if (!version) throw new Error("Dataset version not found");
    const valid = version.rows.filter((r) => r.problems.length === 0);
    const scoped = locationId
      ? valid.filter((r) => r.normalized.location_id === locationId)
      : valid;
    if (locationId && scoped.length === 0) {
      throw new Error(`No approved directory listings found for office ${locationId}`);
    }
    return {
      version_id: versionId,
      location_id: locationId ?? null,
      snapshot_token: `snap-${versionId}-${locationId ?? "ALL"}`,
      directory_count: scoped.length,
      unresolved_issues_count: state.cases.filter(
        (c) => !["verified", "resolved", "deferred"].includes(c.status)
      ).length,
      quarantined_count: version.rows.filter((r) => r.problems.length > 0).length,
      reviewed_corrections_count: state.cases.filter((c) => c.status === "verified").length,
      directory_sample: scoped.slice(0, 5).map((r) => r.normalized),
    };
  },

  async buildExportPayload(
    versionId: string,
    format: "json" | "csv",
    locationId?: string | null
  ): Promise<{ filename: string; content: string; mimeType: string }> {
    const version = state.versions[versionId];
    if (!version) throw new Error("Dataset version not found");
    const valid = version.rows
      .filter((r) => r.problems.length === 0)
      .map((r) => r.normalized)
      .filter((r) => !locationId || r.location_id === locationId);
    const scopeSuffix = locationId ? `-${locationId.toLowerCase()}` : "-all";
    if (format === "json") {
      return {
        filename: `approved-directory-${version.delivery.period}${scopeSuffix}.json`,
        content: JSON.stringify(
          {
            version_id: versionId,
            period: version.delivery.period,
            location_scope: locationId ?? "ALL",
            row_count: valid.length,
            records: valid,
          },
          null,
          2
        ),
        mimeType: "application/json",
      };
    }
    const headers = ["record_id", "npi", "provider_name", "location_id", "address", "city", "state", "zip", "phone"];
    const lines = [
      headers.join(","),
      ...valid.map((r) => headers.map((h) => JSON.stringify(String(r[h] ?? ""))).join(",")),
    ];
    return {
      filename: `approved-directory-${version.delivery.period}${scopeSuffix}.csv`,
      content: lines.join("\n"),
      mimeType: "text/csv",
    };
  },
};
