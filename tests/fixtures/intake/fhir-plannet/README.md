# Synthetic FHIR contract examples

These authored synthetic fixtures test the **FHIR R4 / Da Vinci PDEX Plan-Net 1.2.0** subset parser. Names, contacts, and `example.invalid` URLs are strictly synthetic. Acceptance in the workbench does not certify external profile or terminology conformance.

- `north-south.json`: nine resources, including one clinician, two locations without NPI, explicit roles, a source network, an unresolved role, and an unsupported `InsurancePlan`.
- `expected.json`: independent NORTH/SOUTH expectations, exact contributing locators, and planned adverse variants.
- `interface-examples.json`: illustrative upload, preview, acceptance, projection, and conflict payloads matching [API_REFERENCE.md](../../../../docs/API_REFERENCE.md).
- `profile-location.json`: standalone `Location` specimen for pinned profile checks.
- `profile-graph.json` & `profile-graph-expected.json`: coherent eight-resource Plan-Net 1.2 clinician/clinic/payer/Network/NORTH/SOUTH/roles graph with separate role and office phones.
- `profile-graph-multiple-networks.json`: cardinality counterexample where NORTH is withheld from automatic office projection while SOUTH remains usable.

See [FHIR_AND_STANDARDS.md](../../../../docs/FHIR_AND_STANDARDS.md) for supported resources, boundaries, and NPI check-digit scope.
