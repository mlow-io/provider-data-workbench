# Source onboarding and normalization recipes

The sections below describe implemented recipes and MCP tools. D3's selected invocation contract is appended below; [STATUS](../STATUS.md) distinguishes its implementation from controlled and actual-model verification. Native FHIR validation is separately owned by [the FHIR contract](FHIR_INTAKE_CONTRACT.md), not the clinic recipe language.

## Operator workflow

Receive a clinic CSV/XLSX or flat-JSON file through Intake. Existing parsing choices select its worksheet/header/encoding/delimiter. Open **Profile and normalize** to inspect complete column counts and bounded examples. Null, blank and absent cells have separate counts. Header alias suggestions are editable and do not establish field meaning or provider identity.

Map canonical provider fields, choose explicit rules and preview. Phones retain extensions separately, ZIP codes retain leading zeros and ZIP+4, and source dates require a declared format. Preview includes full valid/quarantined counts, paginated rows and field transformations. Large examples are explicitly labeled truncated; originals and dataset downloads retain complete values.

Enter a name, reviewer and reason to save an immutable proposal. Explicit approval creates another immutable revision. Applying it creates a new intake attempt, not accepted observations. Review the regular intake preview and use its separate acceptance actor/reason/policy. Download the validated dataset after acceptance. Restart and repeats preserve source bytes, revisions, attempts and accepted lineage.

Pending agent proposals appear in the panel. Load one, inspect its saved attribution, preview against the current attempt, and enter the separate approval reviewer/reason. Older-attempt proposals cannot be approved; copy their rules into a new proposal and review again. Reviewer identities remain local assertions, not authenticated users.

## Recipe syntax

```json
{
  "version": 1,
  "mapping": {
    "npi": "Practitioner ID", "provider_name": "Clinician name",
    "address": "Office address", "city": "Town", "state": "Region",
    "zip": "Postal", "phone": "Office Tel",
    "record_id": "Source record", "location_id": "Office ID"
  },
  "transforms": {
    "provider_name": ["trim", "collapse_spaces"],
    "state": ["state_us"], "zip": ["zip_us"], "phone": ["phone_us"]
  },
  "required": ["npi", "provider_name", "address", "city", "state", "zip", "phone"]
}
```

Operations are `trim`, `collapse_spaces`, `uppercase`, `lowercase`, `phone_us`, `zip_us`, `state_us`, and `{"op":"date","format":"%d/%m/%Y"}`. Date formats are explicitly `%d/%m/%Y`, `%m/%d/%Y` or `%Y-%m-%d` for `source_updated_at`. Phone/ZIP/state operations apply to corresponding fields. Definitions canonicalize to operation objects. No executable expressions or inferred replacements are accepted.

Each source column maps to at most one canonical field. At most 64 source columns, 256 characters per column name and 32 operations per field are allowed. Existing application-required fields remain mandatory even when a recipe's own required list omits them. Errors retain pre-operation values and add findings. Missing header drift blocks acceptance. Recipes are scoped by exact source namespace, input profile and dataset scope.

Native NPPES/CMS adapters and network bindings keep their existing interpretation. This recipe surface supports clinic CSV/XLSX/flat JSON. Reconciliation and change-impact analysis are implemented and connected in the qualified three-source journey (historical reference retained separately); native adapters and reviewed network bindings remain distinct from clinic recipe normalization.

## Local MCP setup

Install the optional adapter in the repository's environment:

```bash
python3 -m pip install -e '.[mcp]'
```

The adapter targets the official Python SDK 1.x API, pinned to `mcp>=1.14,<2`; SDK 1.14.0 and clean-environment SDK 1.30.0 are tested with real stdio clients. SDK 2 migration is a separate compatibility change. Open the workbench first so its schema is current. Example local client configuration:

```json
{
  "mcpServers": {
    "provider-ingestion": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "provider_directory_truth_layer.mcp_server"],
      "env": {"PDTL_ROOT": "/absolute/path/to/printed-demo-root"}
    }
  }
}
```

Use the actual installed interpreter and launcher's retained root. `PDTL_DB` optionally selects the database; matching artifacts are required. MCP attaches only to a current existing schema and does not migrate, reseed or run interruption recovery against the HTTP service. Logs use stderr; stdout carries protocol messages.

Twelve tools are exposed: eight list deliveries, return the target schema, inspect profiles, preview recipes, list scoped revisions, inspect issues, compare a delivery and save a proposal; four comparison tools inspect comparison profiles, list runs, inspect a run and page typed candidates. Read results are bounded. Inputs use retained receipt IDs, not arbitrary filesystem paths or URLs. The exposed mutation creates a proposal attributed `MCP agent proposal`; retries create distinct proposals. Approval/application/acceptance are absent from this adapter. Service checks enforce boundaries independently of tool annotations.

Example request: “Inspect this delivery, explain uncertain bindings, propose explicit phone normalization and show its preview. Save a proposal for review.” Source cells are untrusted data, never instructions to execute.

## Verification

With the MCP extra installed, run:

```bash
python3 -m pytest -q tests/test_normalization_recipes.py tests/test_onboarding_service.py tests/test_mcp_onboarding.py
npm run test:e2e --prefix web -- normalization.spec.ts
```

The protocol test starts a real stdio server and checks discovery, profiling, preview, unsupported-operation rejection and proposal-only persistence. A coexistence regression preserves a live processing marker and recovery report. Browser tests exercise desktop/phone normalization, separate decisions and inspected dataset values.

The [synthetic fixtures](../tests/fixtures/onboarding/) include hand-authored transformation expectations and ambiguous identities. [MCP evaluation questions](../tests/fixtures/onboarding/mcp-evaluation.xml) define stable read-only tasks for a configured model/client. Protocol/browser tests do not establish model mapping quality; report the actual model and outcomes separately when those questions are run.

## D3.0 selected model invocation contract

Selected 2026-11-14 before implementation. One experimental OpenAI Responses API route proposes clinic column bindings and existing normalization operations. Use `gpt-5.6-terra`, reasoning `none`, standard service, no tools/conversation/background/streaming and `store=false`. Current [model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra) supports Responses and structured outputs; its published standard text rates are $2 input / $12 output per million tokens, with cache-write input at 1.25 times the input rate. [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) constrain the response shape; deterministic recipe and source-column validation remain mandatory. These are configuration/pricing assumptions checked on this date, not a live-model result or an invoice guarantee.

The application reads only `OPENAI_API_KEY`, with explicit `PDTL_ASSISTANT_ENABLED=1`. Neither is supplied through HTTP, retained request bodies or exports. The fixed destination is `https://api.openai.com/v1/responses`; redirects and arbitrary endpoint/model/header overrides are rejected. A test-only injected transport uses controlled responses without production credentials. No other application's credentials are discovered or reused.

Every run requires current `expected_attempt`, actor, reason, request ID and `external_processing=true`. The exact source namespace/profile/scope/retained artifact and sample locators are pinned locally. Synthetic receipts are eligible by default; other designations additionally require the exact namespace in server configuration `PDTL_ASSISTANT_ALLOWED_SOURCES` (comma-separated). This is local processing permission, not a general healthcare/privacy certification. A receipt may not be a network roster or native reference profile.

Send at most 40 source columns and the first three retained rows, with at most 160 UTF-8 bytes per sampled cell; mark clipping explicitly. Keep null/blank/absent distinctions and source row locators. No original workbook, entire directory or unrelated receipt is transmitted. Decline oversized/ambiguous headers rather than silently omitting columns. Source cells and headers are untrusted data. Instructions forbid following their embedded commands or inventing facts. Required acceptance fields come from application policy, not model choice.

The strict output shape is `{bindings:[{field,column,operations:[{op,format}]}],unresolved:[{field,reason}],explanation}`. Canonical fields, existing source columns, operation names and date formats are enumerated. Non-date formats must be null. Duplicate fields/columns, unknown keys, invented source columns, unsupported operations, nonfinite/duplicate-key JSON, refusal, incomplete response, absent/invalid usage or unexpected tool output fail visibly. Unmapped required fields must be acknowledged as unresolved. A syntactically valid but semantically incorrect proposal still requires human review; schema validation cannot establish that a phone belongs to an office rather than a fax.

Bounds: one provider call per run, 18,000-byte complete request, 2,048 maximum output tokens, 256 KiB response, ten-second socket timeout and thirty-second active-call acceptance ceiling, checked while reading and after the call. A blocked read can take up to one socket timeout to return after that ceiling; an overrun cannot publish a proposal. Before calling, reserve $0.08 against a $1 lifetime allowance in that workbench database, including failed/unknown-outcome calls. The estimate conservatively reserves 20,000 input tokens at the documented cache-write ceiling plus the output limit, rounded upward. Request/token caps and the local reservation are application bounds; external billing and future price changes require separate verification. Store actual usage and a conservative rate-based estimate when available, never claim invoice-exact cost. No automatic retries or refunds for uncertain calls.

Schema 13 adds `assistant_run` (idempotent intent, receipt/attempt, configuration/context, request/response artifacts, state/revision, budget reservation, result and proposal pointer) and append-only `assistant_run_event`. Back up populated schema 12 before migration; preserve verification/restore of stopped schema-11/12 archives. Reuse the existing artifacts and local worker lock. Creation makes no network request. States: queued, running, response_ready, succeeded, failed, cancelled and unavailable. A disabled/unconfigured client records unavailable. An explicit worker call handles one invocation and proposal publication. A process dying in running has unknown external outcome and becomes failed on the next owned pass, with no replayed API call; a journaled response_ready result can be validated/published after restart without another invocation. Revision checks fence cancellation and stale receipt attempts. Proposal insertion, result pointer and success event commit together; failure leaves no proposal. Every source artifact, request, response and run event remains inspectable.

Implemented HTTP surface: GET receipt-scoped `/assistant-runs` lists configuration/availability and runs; POST creates a run with the fields above; GET `/assistant-runs/{id}` returns its retained packet; POST `/{id}/run-once` explicitly invokes/resumes; POST `/{id}/cancel` requires revision/actor/reason. A completed proposal appears in the existing recipe selector, with run attribution and unresolved fields. Loading the editor or refreshing history does not invoke a model. Approval, application and dataset acceptance remain distinct existing decisions; runs have none of that authority.

Freeze `tests/fixtures/onboarding/mapping-assistant-v1.json` and its manifest before any actual model trials. Compare exact field bindings, abstentions and cleaned values with independent authored expectations and the current alias-only baseline. Include reordered/messy headers, ZIP/extension preservation, dates, ambiguous contact numbers and instruction-like cells. Record raw per-case outputs, validation failures, missing/incorrect bindings, corrections needed, latency and available usage/cost, with denominators. Do not label correction counts as measured human effort. Gates are zero invalid operations reaching acceptance and zero incorrect automatic state changes. Keep the feature experimental/disabled while benefit is unproven. Missing API access leaves actual-model A1/A3 open; controlled transport tests are separate evidence.
