# Saved FHIR directory intake contract

Status: D1.1 pure parser and offline inspection CLI implemented, 2026-11-14. Pinned offline and online validation reports exist for valid, warning and invalid controls; the standalone Location now has no online errors/warnings. Application-wide conformance remains unverified. D1.2 upload/API, durable reference acceptance and comparison/export integration are implemented headlessly. D1.3 native UI is implemented and headlessly verified; no migration has been added. [NEXT](../NEXT.md) owns the active brief. Product scope comes from [SPEC](../SPEC.md), shared boundaries from [ARCHITECTURE](ARCHITECTURE.md).

## Purpose and bounded input

Import one saved UTF-8 JSON FHIR R4 4.0.1 `Bundle` with `type=searchset`, interpret the declared Plan-Net 1.2.0 subset, and let an analyst review supported evidence through the existing workbench. Reuse the current 10 MiB artifact limit; start with a planned 1,000-entry limit per import and reject excess input visibly. These limits bound local work and must be shown in source setup. Changes to limits require an explicit contract revision and measured validation.

The API accepts profile `fhir-plannet-r4`; the native GUI exposes separate resource review and acceptance. D1 accepts saved bytes only. It never follows pagination/reference URLs, calls a terminology server implicitly, or treats a saved response as a fresh fetch. Saved metadata includes a declared source namespace and optional known endpoint/query context; absent endpoint context stays unknown. A local filename is not evidence of a remote origin.

Retain unsupported Bundle types as visible unsupported input, not empty valid imports. Diagnostic OperationOutcome entries are retained as findings rather than provider observations. Non-object or malformed entries retain their locator and failure; one malformed entry cannot silently disappear from counts. Unknown resources/extensions remain in the exact artifact and support report.

## Declared resource and field subset

All resource fields remain in retained originals. The following is the initial interpretation/projection scope, not a claim of full profile support.

| Resource | Interpret for this slice | Explicit boundary |
|---|---|---|
| Practitioner | Identifier system/value, names, active flag, available resource version and source-update metadata | Do not copy personal contact/address into an operating office; missing NPI does not turn the resource into an organization |
| Organization | Identifiers, names, active/type and source contact/address evidence | Distinguish Network using declared profile/type evidence; do not create a reviewed local organization/network binding automatically |
| Location | Identifier, name, status, structured address, telecom and managingOrganization reference | Keep contact/use/period metadata; do not collapse multiple phones into one presumed current value |
| PractitionerRole | Practitioner, organization and location references; active/period; role/specialty codings; telecom; Plan-Net network-reference extension | Missing practitioner is unresolved clinician linkage, not proof the organization is the clinician; retain role scope and do not infer combinations |

Network is a Plan-Net profile of Organization. Support `http://hl7.org/fhir/us/davinci-pdex-plan-net/StructureDefinition/network-reference` explicitly. Retain other extensions as uninterpreted; unknown `modifierExtension` or `implicitRules` blocks affected operational projections pending supported interpretation. InsurancePlan, OrganizationAffiliation, HealthcareService and Endpoint remain unsupported semantic content. No accepting-new-patients interpretation or clinical credential/qualification determination is included in D1.

Source references checked on 2026-11-14: [FHIR R4 Bundle](https://hl7.org/fhir/R4/bundle.html), [Plan-Net artifacts](https://hl7.org/fhir/us/davinci-pdex-plan-net/STU1.2/artifacts.html), [Plan-Net PractitionerRole](https://hl7.org/fhir/us/davinci-pdex-plan-net/STU1.2/StructureDefinition-plannet-PractitionerRole.html). Implementation must pin the package/validator versions and document the supported fields/extensions against these artifacts; reading the guide is not validation evidence.

## Parser result and identity contract

The pure parser returns a versioned object with `resources`, `references`, `assertions`, `findings` and `coverage`. It is input to the service's native preview envelope defined below; it is not itself an HTTP response.

| Collection | Minimum contents |
|---|---|
| Resources | Entry locator, fullUrl, type/id, available meta.versionId/profile/lastUpdated, original object, supported kind and validation findings |
| References | Origin resource and JSON field path; raw target; resolved target locator or explicit unresolved/ambiguous/unsupported reason |
| Assertions | Typed subject/context, field/value, all supporting resource/field references, interpretation rule version and eligibility/findings |
| Findings | Stable code, severity, affected locator, explanation and consequence for parsing, comparison or acceptance |
| Coverage | Entry/resource counts, supported/unsupported/invalid/unresolved counts, saved query/next-link context and bounded/unknown completeness |

Storage assigns receipt/attempt IDs; the parser does not open the database. A retained resource reference is anchored to its immutable attempt and entry locator. A source identity is scoped by source namespace, known endpoint context, resource type/id and available version information; it is not a local reviewed identity. Missing or duplicate source IDs never destroy entry-level provenance.

D1 resolves unambiguous within-Bundle fullUrl references, relative type/id references where the source context permits, and matching URN fullUrls. It performs no network resolution. Contained `#id`, identifier-only, version-specific and external references that the initial resolver does not support remain explicitly unresolved/unsupported. Conflicting matches never use a last-write-wins rule. Distinguish duplicate conflicting entries from different retained source versions; do not silently choose the latest version by lexical ordering.

## Projection into existing comparison

Preserve native resources, then derive limited comparison assertions. Every derived field records its exact source resource and field path. Reuse current clinician/location review after adapting its input contract; do not fabricate a flat original row to fit `make_records`.

Clinician identity values come from the selected Practitioner. Location values come from the selected Location. A role supplies the explicit relationship context. For D1's automatic candidate projection, require unambiguous supported references to one practitioner and one location. Multi-location roles remain inspectable unresolved scope until an explicit supported selection is designed; no Cartesian product of offices/networks is allowed.

Use Location telecom for D1's automatic location assertions. Role telecom remains inspectable role evidence and does not supply an automatic office-phone projection in this slice. Multiple contact values or incompatible use/period remain separate or unresolved rather than silently ranked. No network membership is inferred from NPI, name or shared address. A source Network reference and a human-reviewed local network binding remain distinct.

Keep all contributing references in candidate snapshots, identity/field decisions, freshness checks and JSON/XLSX exports. Changing a contributing source version must invalidate a stale proposed decision according to the existing snapshot rules. The selected scope and the complete Bundle's shared context remain clearly labeled.

## Interpretation, comparison and acceptance

Three separate judgments apply: FHIR/profile validity; suitability for a particular comparison; eligibility for a specific operational action. A resource can be retained and inspected while blocked from automated projection. Existing reconciliation may inspect quarantined evidence; this does not turn it into accepted data.

Source-reference acceptance explicitly records review of eligible evidence. It does not approve a clinic dataset, establish a reviewed identity link, prove participation or create correction work automatically. The new profile uses `reference_resources` as specified below; existing profiles retain `valid_rows`/`reject` semantics.

Malformed envelopes fail interpretation visibly. Unsupported/unresolved content contributes findings and coverage; it cannot be reported as a healthy complete directory. A successful bounded subset may be useful reference evidence when labeled and explicitly reviewed. It is never a complete clinic roster or sufficient evidence for terminating omitted locations.

Profile validation uses a pinned tool/package setup with retained command/version/report. Ordinary offline imports must not require live terminology access. Distinguish validator unavailable, terminology unavailable and profile failure; never report an unavailable check as passed. Diagnostic details must identify which assertion or action is blocked and why.

## UI, service and export integration

Extend existing upload/detail/preview patterns and intake navigation; prefer adding the explicit profile over a second upload application. The operator must see resource type, original locator, declared support, unresolved references, comparison eligibility and scope. Show both counts and bounded samples. Downloads preserve complete selected evidence.

The API remains responsible for validation, expected-attempt checks and atomic acceptance; hiding a button is insufficient. Reuse existing typed 404/409/422 conventions as applicable. [Original interface examples (implemented policy; illustrative identifiers)](../tests/fixtures/intake/fhir-plannet/interface-examples.json) cover upload, native preview, acceptance, multi-resource projection and stale acceptance. Update API_REFERENCE only when these become implemented.

The evidence packet must include all supporting resources/paths for a selected NORTH value and label other Bundle entries as shared context. Existing clinic approved-version exports retain their format and source lineage. A new FHIR evidence packet is not a conformant FHIR export.

## Selected D1.0 integration decisions

D1.2 implements these decisions at the headless service/API/export boundary. A later change requires a documented reason and updated acceptance expectations before dependent code.

### Persistence: reuse schema 11

Retain the Bundle through the existing artifact/receipt service. Store one native row per resource in the immutable attempt preview's `rows`, with its exact resource `original`, `locator`, scoped `native_id`, native `normalized` fields and `problems`. Store the graph's `references`, `assertions`, `findings`, `coverage` and validation summary under `preview.native`, with `format_version=1`. Original bytes remain authoritative, including malformed entries and unsupported content. This bounded graph is read with its attempt; no cross-dataset graph traversal or graph database is needed.

Accept eligible supported resources into existing `observation` rows. Provider/location projections may be null; missing clinic fields do not create fictitious values. A profile-specific acceptance branch must bypass clinic validation and automatic `link_work`/participation generation. Native references stay in the pinned preview, never in the human-reviewed `relationship` table. Existing case/source behavior remains unchanged for old profiles. No schema migration is planned; test populated schema-11 preservation and old-profile reads before qualifying D1.2. Revisit a narrow additive index/table only if measured query/export behavior cannot meet the bounded contract.

`valid_count` counts structurally eligible supported resource rows, not complete provider records or resolved assertions. `native.coverage` separately reports unresolved references, unsupported resources and projection counts. Profile validation is a separate status: `not_run` or `unavailable` must remain visible even if structural evidence is retained/accepted for review. Failed or unsupported semantics block affected projections; acceptance is not profile certification. A zero-result searchset is retained as successful empty evidence, but `reference_resources` rejects a zero-eligible-resource acceptance.

### Comparison: derived records with supporting references

Keep the existing `reference(attempt_id, locator, address_path)` hashing helper. A FHIR clinician reference uses its Practitioner resource locator and empty path. A location comparison reference uses the selected PractitionerRole locator and `location[0]` path, only when its single-location resolution is eligible. Repeated role/source versions remain separate retained references.

The comparison adapter produces the existing comparison fields plus `supporting_refs`: ordered unique `{attempt_id, locator, path, field}` objects for every contributing resource field/context. The role is the comparison record's anchor; it is never represented as an original flat clinician row. Carry `supporting_refs` through cleansing, candidate snapshots, field options/decisions, impact/follow-up evidence and exports. Field-selected evidence includes relevant supporting references and relationship context; complete retained Bundle payloads remain labeled shared context. Use the existing attempt/source snapshot checks, with native parser/projection versions pinned in the attempt fingerprint.

Raw Network references use `source_network_reference`. Existing `network_id` remains null until a reviewed local binding exists. Do not substitute source resource IDs into local database foreign keys. For D1, compare location telecom only; role telecom is retained and displayed but does not supply an automatic office-phone projection. This removes a discretionary contact-precedence rule from the first slice.

### Service: one explicit profile and acceptance policy

Extend `POST /api/intakes/files` with `profile=fhir-plannet-r4`; raw body/filename/source/designation behavior is unchanged. Source namespace is explicit and synthetic demonstration metadata is labeled. Saved input does not gain verified endpoint provenance from its filename or fullUrl. D2 supplies actual retrieval metadata through its owned acquisition adapter.

`GET /api/intakes/{id}` adds `preview.native` only for this profile, while retaining standard receipt/attempt/history/observation fields. Expose bounded resources/findings and complete counts; complete packet exports retain the full native preview. The same profile branches in interpretation and comparison-input creation; recipe mapping/application is rejected for this profile. Reprocessing always creates another attempt.

`POST /api/intakes/{id}/commit` requires `expected_attempt`, `policy=reference_resources|reject`, actor, reason and `request_id` for this profile. Within one transaction, recheck current attempt, validate eligibility, insert observations and save decision/request-intent hash. An identical request retry returns its prior result; changed content under the same request ID or a conflicting terminal decision returns 409. An old expected attempt returns 409 before any write. Existing profiles do not acquire this new request-ID requirement.

A repeat receipt retains a separate delivery and acceptance decision; equal source/profile/scope/artifact/parser fingerprints may reuse original accepted observations through existing duplicate-delivery lineage. Decisions never rewrite the original interpretation. Source acceptance changes no clinic approved-version pointer, identity link, network binding, investigation case or external directory.

## Fixture and validator execution plan

The authored [nine-resource Bundle](../tests/fixtures/intake/fhir-plannet/north-south.json), [independent expected outcomes and negative variants](../tests/fixtures/intake/fhir-plannet/expected.json), and [interface examples](../tests/fixtures/intake/fhir-plannet/interface-examples.json) define the first implementation target. The mixed Bundle is now a retained profile-invalid fixture (four errors); a separate [Location specimen](../tests/fixtures/intake/fhir-plannet/profile-location.json) had zero validator errors and two offline terminology warnings. A later [pinned online run](evidence/canonical/fhir-terminology-2026-11-14/README.md) resolved those warnings; state/status negative controls preserve warning/error distinctions. These fixture results do not establish application-wide conformance. NORTH/SOUTH have distinct location phone paths; neither location has an NPI. An unresolved role and unsupported InsurancePlan remain visible.

Pin the initial validator to [HL7 Java validator release 7.0.5](https://github.com/hapifhir/org.hl7.fhir.core/releases/tag/7.0.5), FHIR `hl7.fhir.r4.core#4.0.1` and `hl7.fhir.us.davinci-pdex-plan-net#1.2.0`. During D1.1, acquire tools/packages into an invocation-owned cache, record hashes, JVM version and resolved package dependency versions, and capture the exact supported CLI invocation and reports. The subsequent headless implementation acquired and ran these tools in an invocation-owned cache; [the evidence manifest](evidence/canonical/fhir-parser-2026-11-14/validation-manifest.json) records package metadata hashes and exact outcomes.

Run validation separately from ordinary intake, with no implicit runtime package downloads or remote terminology lookups. Offline terminology limitations remain explicit findings. Retain at least one profile-valid specimen and intentional profile-invalid/unsupported cases before D1.1 is called complete; correct the authored fixture where necessary without changing its domain expectations. If the pinned tool cannot execute, record the failure and an explicit replacement decision rather than silently using latest. Missing validator/terminology is an open standards gate, never a synthetic pass.

## Acceptance cases

| ID | Expected behavior | Verification boundary |
|---|---|---|
| F1 | Saved searchset is parsed within byte/entry limits; unsupported types, malformed entries and empty results are distinguished | Pure adapter fixtures; originals/hash and complete count assertions |
| F2 | Profile and terminology check outcomes are distinct; supported fields/extensions are explicit; unavailable checks are not passes | Pinned validator reports for authored valid/invalid resources and unavailable terminology |
| F3 | Resource IDs are source-scoped; unresolved/ambiguous references and unsupported modifiers cannot silently resolve | Pure resolver and service fixtures, including duplicate identities and role without practitioner |
| F4 | Location/Organization without clinic-required fields remain inspectable under resource rules | Intake/acceptance integration; existing clinic required-field regressions unchanged |
| F5 | NORTH/SOUTH and role/network scopes remain distinct; every derived phone/address has contributing locators | Authored comparison expectations, multi-location/phone ambiguity and no cross-product fixtures |
| F6 | Explicit review/acceptance, repeat imports and stale actions preserve prior decisions and approved clinic versions | Transaction/restart tests; no automatic link, case, membership or dataset promotion |
| F7 | Selected evidence exports retain all supporting references and distinguish shared Bundle context | Inspect JSON and XLSX contents, source paths, versions and NORTH/SOUTH scope |
| F8 | An analyst completes upload → findings → selected evidence → review → export through existing screens | Browser journey at supported widths, meaningful error/empty/stale states and restored selection after restart |

Pure-parser and CLI coverage is in `tests/test_fhir_intake.py` (78 passing cases). F1/F3/F5 have pure-adapter evidence; F2 has retained offline-unavailable and online positive/negative validator outcomes in [the terminology receipt](evidence/canonical/fhir-terminology-2026-11-14/README.md). F4/F6/F7 now have headless service/export evidence in `tests/test_fhir_store.py` (20 cases); F8 now has desktop/phone native workflow evidence in [the web receipt](evidence/canonical/fhir-web-2026-11-14/README.md); untested standards/profile coverage remains unverified. See [the parser receipt](evidence/canonical/fhir-parser-2026-11-14/README.md) for commands and boundaries.

## Coherent provider graph (R2)

Freeze the next positive fixture before implementation: eight synthetic resources in fixed order, Practitioner `synthetic-clinician`, Organization `synthetic-clinic`, Organization `synthetic-payer`, Network Organization `synthetic-network`, Location `north`, Location `south`, PractitionerRole `role-north`, PractitionerRole `role-south`. Use checksum-valid synthetic identifier `1000000004` (not a registry-existence claim), ZIP `02108`, NORTH phone `617-555-0100` at `10 Example St`, SOUTH `617-555-0200` at `20 Example St`. Each role explicitly references the clinician, clinic, its own location and the source Network. The Network's parent is the payer Organization; local network ID stays unknown.

Declare Plan-Net 1.2.0 profiles and all required inherited fields, source-specific IDs, explicit synthetic narratives and complete within-Bundle references. The whole searchset has two role matches and six includes, a self link and exact total=2. Clinic/payer types use the pinned OrgTypeCS `prvgrp`/`payer`; Network uses required `ntwk` and a declared parent. This is source relationship evidence, not a local identity approval. Independent expected locators/values must be authored before parser/validator qualification. Preserve `north-south.json` and its invalid/unsupported/unresolved cases unchanged.

G1–G4 are owned by NEXT. The pinned validator must inspect the whole graph, preserving any warning/error and exact command/version/digests. Service tests must inspect actual native observations, separate identity/field decisions, NORTH/SOUTH phone/locator scopes and real JSON/XLSX payloads after restart, without silently creating clinic cases, approved datasets or local network bindings. Actual HAP role observations are a separately bounded source check and are not committed as synthetic fixtures or certified by a positive synthetic report.

The positive graph explicitly uses version-qualified profile canonicals (`profile-URI|1.2.0`) as defined by [FHIR R4 canonical references](https://hl7.org/fhir/R4/datatypes.html#canonical), separate from each resource's own `meta.versionId`. Network classification recognizes the existing bare canonical or that exact supported version. Other explicit version suffixes remain unresolved under the declared subset; they are not silently stripped or treated as certified support. Supporting the newly distinguished representation changes native interpretation to `fhir-plannet-r4-v2`; original v1 attempts/observations stay immutable until an explicit new interpretation. No schema migration or reprocessing on service startup is introduced.

The first R2 graph draft failed pinned validation: its initial `1000000001` sample had an invalid NPI check digit and roles lacked their required contact/Endpoint choice. Preserve that exact draft/report separately, then correct only the new positive specimen to checksum-valid `1000000004` and role contact phone `617-555-0300`. Location phones remain the distinct NORTH/SOUTH values; role contact does not replace office contact in automatic projection. The [CMS check-digit specification](https://www.cms.gov/Regulations-and-Guidance/Administrative-Simplification/NationalProvIdentStand/Downloads/NPIcheckdigit.pdf) defines the Luhn rule; checksum validity does not establish an actual provider or credentials. Original D1/D4 fixtures and their declared shape-only limits are unchanged.

The bounded live role contains three explicit Network-reference extensions. The pinned Plan-Net 1.2.0 PractitionerRole slice has maximum cardinality 1. Preserve this as an unsupported projection under the declared target, without asserting that the source satisfies or violates another guide version. R2 adds a separate synthetic multiple-Network counterexample and a precise cardinality diagnostic. The affected role produces no office assertion; other independently valid roles remain usable. Keep all source Network resources/references, local `network_id=null`, and the separate unresolved unsupported HealthcareService reference. Do not broaden the supported cardinality or infer a preferred Network to force the actual source through.
