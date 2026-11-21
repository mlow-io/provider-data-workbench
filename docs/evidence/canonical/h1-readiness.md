# H1 readiness receipt — 2026-11-03

Baseline: public main `086425a`. Documentation preparation only; all inputs and contact assertions are synthetic. No participant was observed and no human timings or usability results are claimed.

## Checks performed

From the repository root, fresh setup and resumption both exited successfully:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src python3 scripts/demo.py --prepare-only
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=src python3 scripts/demo.py --root '<printed-root>' --prepare-only
```

The second command used the exact root produced by the first. These checked preparation and reuse, not live launcher start/stop behavior. The documented CSV derivation produced one NORTH row with listed phone `6175550177`; it retained the original sample inputs. Independent read-only database inspection found zero receipt, work_case and work_event rows in the prepared root.

Focused browser command:

```sh
PATH="$PWD/.venv/bin:$PATH" npm run test:e2e --prefix web -- guided-first-review.spec.ts investigation.spec.ts --project=wide
```

Result: two tests passed in 19.6 seconds. These are separate guided-review and investigation scenarios, not one uninterrupted participant walkthrough. Console results were observed through the execution tool; no standalone browser log was retained for this invocation.

Documentation validation: `python3 scripts/check_project_docs.py` and `git diff --check` passed. The unchanged public application baseline also passed the [complete CI workflow](https://github.com/mlow-io/provider-directory-workbench/actions/runs/41724410383).

## Remaining gate

Use the [walkthrough kit](../../INVESTIGATION_DEMO.md) with an actual participant, a fresh synthetic root and private observation notes. H1 remains open. Record assistance and partial outcomes honestly; select at most one observed problem for the next implementation brief.
