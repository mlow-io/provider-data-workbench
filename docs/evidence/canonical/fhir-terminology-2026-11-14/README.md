# Pinned online terminology controls — 2026-11-14

This supplements the preserved [offline validator receipt](../fhir-parser-2026-11-14/README.md). The application parser and ordinary imports remain offline and report profile/terminology checks as `not_run`; external fixture qualification does not certify an accepted source receipt.

## Actual checks

Validator **7.0.5**, FHIR **4.0.1**, Plan-Net **1.2.0** and the same authored Location were used with `https://tx.fhir.org/r4`. The JAR digest remains `9dfe9f305b0f9389eceade2a4a1c9a2740d7b0e614066fdf07a78b571c76d92f`. An independent APFS clone of the prior pinned package home preserved the original cache. New transaction cache/log/report files were invocation-owned. Each process had a 120-second outer timeout and a 30-second validation timeout; none timed out. See [the manifest](manifest.json) for exact input/report hashes, command template, durations and selected actual terminology outcomes. The [HL7 validator entrypoint](https://hl7.org/fhir/validator/) and [validator project security/access documentation](https://github.com/hapifhir/org.hl7.fhir.core/blob/master/SECURITY.md) identify the tooling and public terminology service.

| Synthetic input | Exit | Actual issues | Meaning |
|---|---|---|---|
| [Standalone Location](../../../../tests/fixtures/intake/fhir-plannet/profile-location.json) | 0 | Zero errors/warnings; one informational `All OK` | [Online report](online-location-validation.json); previously two offline USPS warnings. Actual terminology response validates `MA` as Massachusetts. |
| [Invalid state control](../../../../tests/fixtures/intake/fhir-plannet/profile-location-invalid-state.json) | 0 | One warning, zero errors | [Report](invalid-state-validation.json); actual response returns false for `ZZ`. The extensible state binding generates a warning rather than a process failure. Exit 0 alone is insufficient evidence of a clean resource. |
| [Invalid required status](../../../../tests/fixtures/intake/fhir-plannet/profile-location-invalid-status.json) | 1 | Three errors | [Report](invalid-status-validation.json); invalid LocationStatus membership and the profile's fixed active status fail. |
| [Original mixed Bundle](../../../../tests/fixtures/intake/fhir-plannet/north-south.json) | 1 | Four errors, eleven warnings, two informational issues | [Report](mixed-bundle-validation.json); intentional Network type/parent defects and dependent role profile failures remain. Warnings concern narratives/search metadata; online terminology does not repair profile defects. |

The two negative Location specimens differ from the original only in state=`ZZ` or status=`not-a-status`. They were generated in the owned runtime, validated there and then retained as repository fixture files with the same input digests. Original fixtures and offline reports are unchanged. Sanitized [Location](location.log), [state](invalid-state.log), [status](invalid-status.log) and [Bundle](mixed-bundle.log) process logs accompany the reports. Complete transaction logs remain locally retained; their hashes and selected result/code/system/display/message fields are in the manifest. Only synthetic data was sent to the terminology service; no model or payer request is part of these four checks.

## F2 boundary

F2 now has observed pinned online profile/terminology outcomes for its valid specimen and intentional warning/error controls, alongside unavailable-offline outcomes. This resolves the standalone specimen's prior offline terminology gap. It does not establish support for untested code systems/profiles, all Plan-Net resources, actual payer conformance or the full application. New ordinary imports still have `not_run` validation states unless a separately designed validation integration is added. No runtime validation service or dependency was introduced.

The first negative state experiment demonstrated why severity must be inspected: its nonmember code yielded a warning and exit 0, so a separate required-code control was added and failed as expected. A current-state audit script also initially mistook the backup manifest's registered-artifact count for a list; reading its actual artifact map corrected the check and all twelve source/restored hashes matched. Neither issue changed application data or the earlier qualification results.
