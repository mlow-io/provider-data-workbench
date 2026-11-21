# Next brief: actual-model evidence when configured

Updated 2026-11-15. Independent R1–R4 headless work is complete and locally organized; [STATUS](STATUS.md) and [the final receipt](docs/evidence/canonical/integrated-review-2026-11-15/README.md) identify the exact checks and implementation commit. GitHub publication of the reviewed candidate was authorized on 2026-11-15; repository refs and CI record its delivery. This brief does not authorize extra source families, broader cardinality, a new framework or hosted deployment.

## Entry condition

A1/A3 require an approved API key supplied through `OPENAI_API_KEY` and explicit `PDTL_ASSISTANT_ENABLED=1`. The latest check found both absent/disabled. Do not borrow app/session credentials or substitute controlled responses for an actual-model result. Normal/manual operations and deterministic evaluation remain usable without access. No further software work is blocked behind access within the completed R1–R4 scope.

## Bounded task and acceptance

Read AGENTS/SPEC/ROADMAP and the [mapping contract](docs/SOURCE_ONBOARDING.md#d30-selected-model-invocation-contract). Use a new owned root whose parent exists:

```sh
provider-truth-layer evaluate-mapping --root .runtime/mapping-actual-NEW --invoke-model
```

Keep the frozen eight-case corpus/digest and current model/prompt/schema/budgets. Perform at most its existing one-call-per-case bound; preserve raw responses, invalid outputs, unavailable/unknown outcomes, actual usage/latency and all failed attempts. Inspect proposed recipes and independently scored bindings/abstentions/corrections/cleaned values against the unchanged deterministic baseline. Zero invalid operations may reach acceptance and zero automatic approvals/state changes are permitted. Update the model receipt/STATUS/case study honestly; no unobserved human-effort improvement claim. Keep assistance experimental/disabled if usefulness is unsupported.

## Independent gates and stop boundary

H1 uses the existing investigation walkthrough; H2 now has a [prepared-state observer kit](docs/OPERATIONS_DEMO.md#h2-prepared-state-observer-kit). Both require actual uncoached participants. Broader actual-source/profile validation needs a specific named task, not a crawl or resource expansion. Publication of this reviewed candidate is authorized; hosted deployment and additional product scope require separate decisions. Preserve all original histories, fixtures, runtime/failed-run evidence and local commits; no automatic cleanup or reseeding.
