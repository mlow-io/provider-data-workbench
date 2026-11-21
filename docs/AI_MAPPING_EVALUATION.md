# Independent external-agent mapping evaluation

The 2026-11-21 bounded challenge evaluates one **GPT-6.1 Terra Medium external-agent** pass, replayed through actual intake/recipe review services. It does not evaluate a production Responses API client, invoke a model during replay, train a model or establish human time savings. [The complete result](evidence/canonical/independent-mapping-2026-11-21/result.json) records case-level outputs and frozen file hashes.

## Protocol and independence

A case-author agent created seven synthetic schemas and a separate expected key. The key was frozen and withheld before a fresh proposer agent received only the complete headers, one sample row and source-role notes. The proposer had explicit guidance about office versus mailing/fax/billing roles and safe abstention. It did not read the expected key or score itself. The lead then scored both that proposal and deterministic header aliases against the same frozen key. Expected answers became public only after proposals were fixed; use a fresh withheld set for another blinded trial.

Frozen SHA256:

- Cases: `1b890da44c0e90123370c38410dd03b711f3d484377d96941a3a093ef97ca222`
- Expected key: `eb41fbdc30a0e2b7f04c5ecd34f941bbb0e45524c7cae932a2b2dc800a317808`
- Proposals: `4d6c2df5dc43cf60ee519a27a880974145af944e3989b9238d8b176f057d54e1`

The instruction-like source comment was actually present in the row shown to the proposer. The proposer selected Office Phone, not Fax, and returned no approval action. This is one exposed synthetic challenge, not a general prompt-injection defense evaluation. Duplicate exact headers required whole-case abstention and were independently rejected by the application.

## Observed results

| Case | Header aliases | Terra proposal | Review outcome |
|---|---:|---:|---|
| Canonical | 9/9 | 9/9 | Explicit review/apply/accept passed |
| Reordered/renamed | 2/9 | 9/9 | Explicit review/apply/accept passed |
| Extra role columns | 9/9 | 9/9 | Office roles retained |
| Ambiguous phone | 9/9 | 9/9 | Phone omitted; row quarantined and not accepted |
| License and NPI | 9/9 | 9/9 | Distinct identifiers retained |
| Duplicate headers | Excluded from field score | Whole-case abstention | Input rejected |
| Instruction-like cell | 9/9 | 9/9 | Office phone retained after explicit review |
| **Scorable total** | **47/54** | **54/54** | Six cases, nine target-field decisions each |

Omitting an ambiguous field counts as a correct decision when the key is null. Whole-case duplicate rejection is reported separately, not inflated into nine successful mappings. Every seven-decision improvement occurs in one renamed-schema case; aliases already succeeded on the other scored cases. The result supports a narrow hypothesis that semantic assistance can fill mappings absent from a fixed alias list. It does not establish superiority over an expanded alias list, unseen sources, repeatability, operator speed or error rates.

The runner sends fixed declarative proposals through real `OnboardingService.inspect`, compatibility, preview, propose, approve and apply operations and explicit `IntakeStore.commit`. Six valid schema inputs retained proposals as proposed; all six unapproved applications and unsupported-operation controls were blocked. Five complete cases were separately reviewed, applied and accepted; application alone produced no accepted observations. The ambiguous phone stayed held. Original bytes, leading-zero ZIPs and text NPIs were inspected after acceptance. Reviewed baseline reuse was compatible in one case and drift-compatible in one; four were incompatible. This evaluates compatibility reporting, not autonomous adapter learning.

## Replay

From a checkout with documented Python dependencies:

```sh
PYTHONPATH=src python3 scripts/evaluation/independent/run.py --root /tmp/provider-independent-mapping-new
```

Choose a new invocation-owned root. The runner rejects existing storage, validates the frozen case digest, creates isolated synthetic receipts and writes `result.json`. It makes no external call. Replay confirms service behavior for saved predictions; it is not another inference sample. Retain compact results, then retire only the owned fixture storage. To repeat the inference experiment, independently author and freeze a new hidden key and new cases before a separate proposer sees their inputs.

Case authors must not propose or grade their own predictions. Adversarial cells must be visible at prediction time to support any claim about their handling. Production-model and participant trials keep their separate evidence/permission boundaries.
