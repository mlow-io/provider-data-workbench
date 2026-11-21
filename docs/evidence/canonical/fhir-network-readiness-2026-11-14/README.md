# D2 source readiness probes — 2026-11-14

Read-only public-source investigation during final D1.3 qualification. This is endpoint-selection evidence, not an implemented acquisition adapter or successful provider-data import. [Probe hashes/statuses](checks.json) identify locally retained responses without publishing source bytes or machine-local paths.

[HAP official Provider Directory documentation](https://api.hap.org/providerdirectoryapi) publishes `https://provider-directory-r4.api.hap.org` as production and describes unauthenticated, throttled directory reads. Its documentation names Plan-Net 1.0.0; this project's saved-source target is 1.2.0, so source version compatibility must remain explicit and unqualified until assessed. These are separate facts, not a compatibility certification.

A bounded GET to `/metadata` returned 302 to `/metadata/`. No automatic redirect was followed. The manually checked same-host canonical metadata URL returned a FHIR R4 4.0.1 CapabilityStatement with general resource declarations and no `implementationGuide` version. This proves only that this URL supplied R4 metadata. It does not establish the available provider records or Plan-Net profile conformance.

A bounded `GET /Location/?_count=1` returned HTTP 429 and HTML. No provider observation was accepted and no retry loop or further source requests followed. Retain this as throttling evidence. A future connector must respect Retry-After and persisted retry policy rather than misclassifying the response as an empty successful searchset.

One alternative was inspected: [Network Health's official endpoint page](https://www.networkhealth.com/legal/interoperability-apis) publishes its PlanNet base. A metadata read returned HTTP 500 with a Bulk Publish ID validation error. This does not prove the provider-data route itself is broken. No alternate endpoint search or broad crawl was attempted.

Use HAP as the initial configured source candidate for D2.0's bounded transport contract, with controlled-server development independent of current public throttling. Freeze acquisition persistence/page/reference/retry contracts before implementation; leave actual live-data interoperability open until a later, separately bounded read succeeds. Keep source-advertised versions and supported subset visible; never relabel 1.0.0 data as certified 1.2.0.
