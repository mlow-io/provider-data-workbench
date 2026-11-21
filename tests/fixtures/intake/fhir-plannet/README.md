# Synthetic FHIR contract examples

These are authored examples for the D1 saved-Bundle implementation. They contain no real provider records. Names, contacts and `example.invalid` URLs are synthetic. The mixed Bundle has retained profile-validation errors; `profile-location.json` had zero errors/two offline terminology warnings; later pinned online validation resolved both warnings. The workbench accepts the explicit `fhir-plannet-r4` profile; acceptance does not certify profile/terminology conformance.

- `north-south.json`: nine resources, including one clinician, two locations without NPI, explicit roles, a source network, an unresolved role and an unsupported InsurancePlan.
- `expected.json`: independent NORTH/SOUTH expectations, exact contributing locators and planned adverse variants. These are intended outcomes, not outputs from a parser.
- `interface-examples.json`: proposed upload, preview, acceptance, projection and conflict payloads. Identifier placeholders are illustrative, not callable live requests; implemented endpoints are documented in the API reference.

The authoritative behavior and qualification requirements are in [FHIR_INTAKE_CONTRACT](../../../../docs/FHIR_INTAKE_CONTRACT.md). Parser/service tests implement adverse variants described in `expected.json`; the corresponding receipts identify actual coverage and remaining standards limits.

`profile-location.json` is a synthetic standalone Location specimen for pinned profile validation. See [validation evidence](../../../../docs/evidence/canonical/fhir-parser-2026-11-14/README.md); broader terminology coverage remains incomplete. The [online controls](../../../../docs/evidence/canonical/fhir-terminology-2026-11-14/README.md) preserve positive, warning and error outcomes.

- `profile-graph.json`: coherent eight-resource Plan-Net 1.2 synthetic clinician/clinic/payer/Network/NORTH/SOUTH/roles graph, with version-qualified profiles and separate role/office phones. Pinned whole-graph validation has zero errors/warnings.
- `profile-graph-expected.json`: independent v2 parser/locator/export expectations for that graph.
- `profile-graph-multiple-networks.json`: deliberate cardinality counterexample; NORTH is withheld from automatic office projection while SOUTH remains independently usable.

[The R2 receipt](../../../../docs/evidence/canonical/provider-graph-2026-11-14/README.md) preserves the first invalid draft, corrected graph and multiple-Network validator results. Original mixed/adverse fixtures are unchanged. Synthetic checksum validity is not registry existence or credential verification.
