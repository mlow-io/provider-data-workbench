# Synthetic investigation demonstration

All people, offices, responses and downstream values in this exercise are fictional. Recording outreach sends no messages; submissions and observed verification are manually asserted.

## Retained engineering rehearsal

```sh
PYTHONPATH=src python3 scripts/rehearse_investigation.py --root .runtime/new-investigation
```

Choose a new root every time; existing directories are refused. Inspect `investigation.json` and `investigation.xlsx` (Investigation and Outreach sheets), `phone-review.json` and `lineage.json`. A second bounded delivery changes NORTH and omits SOUTH without closing it. NORTH retains both source observations and has two recorded contact attempts, a proposed number, a simulated submission and an observed mismatch that reopens the case. SOUTH remains unchanged. The script reopens the database and checks the retained case. This scripted rehearsal is not a human usability observation.

## H1: observer setup

The participant must encounter an unworked case. Do **not** use the completed engineering rehearsal root for H1. After installing dependencies as in the [README](../README.md), start from the repository root with the virtual environment active:

```sh
make workbench
```

The launcher prints a newly created `Demo root` and starts the local application. Record the exact printed root in the private observation notes. It owns synthetic inputs, its database and retained artifacts. If ports 8000 or 5173 are occupied, stop and investigate; do not connect the participant to an unknown service. Open the printed URL and leave the application at its initial screen. The launcher enables the synthetic sample picker. Do not preload or accept a participant's intake or record their case decisions.

Create the later delivery from the generated sample in that **same** root. Substitute the exact printed path for `DEMO_ROOT` below; leave the original inputs intact. This command refuses to overwrite its output and uses Python's CSV handling to preserve the header and NORTH row, including its already changed listed phone. The built-in **Synthetic changed delivery** retains SOUTH and therefore does not supply the omission in this task.

```sh
DEMO_ROOT='/replace/with/printed/demo/root' python3 - <<'PY'
import csv, os
from pathlib import Path
root = Path(os.environ['DEMO_ROOT'])
with (root / 'inputs/synthetic-changed.csv').open(newline='', encoding='utf-8') as source:
    reader = csv.DictReader(source)
    fields = reader.fieldnames
    north = [row for row in reader if row['location_id'] == 'NORTH']
if len(north) != 1 or north[0]['phone'] != '6175550177':
    raise SystemExit('Unexpected synthetic fixture; inspect it before continuing')
with (root / 'inputs/synthetic-north-only.csv').open('x', newline='', encoding='utf-8') as target:
    writer = csv.DictWriter(target, fieldnames=fields)
    writer.writeheader()
    writer.writerows(north)
PY
```

The participant can load the initial workbook with the sample picker. At the later-delivery prompt, provide the path `<printed-root>/inputs/synthetic-north-only.csv`; the source namespace must be `synthetic-demo` to compare with the workbook. This is setup information, not a decision about acceptance. Tell the participant where to find the upload control only if necessary, and record the assistance.

Stop the launcher with Ctrl-C when the session ends. To resume the same work, activate the environment and run `PYTHONPATH=src python3 scripts/demo.py --root '<printed-root>'`; this retains the database, artifacts and inputs rather than resetting them. Start a new session with a fresh `make workbench` root. Retain the session root and downloaded handoff until the observer has recorded the result; only its owner may remove that exact, stopped synthetic root after deciding it is no longer needed. Never clean another root or delete database sidecars independently.

## Participant task — share this section only

You are investigating fictional provider directory information. The application is local: no actual office is contacted and no directory is updated. Please think aloud as you work. You may use the synthetic clinic workbook in Intake. Use a fictional reviewer name and do not enter personal or real provider information.

Review the workbook and investigate the NORTH office's phone discrepancy. Explain what the evidence establishes, what remains uncertain, and what you would do next. Record your work and produce a handoff another analyst could use. Ask the observer for the next synthetic input when you are ready; you may also ask for help, which will be recorded.

**Later delivery:** The observer will provide a second synthetic file from the same clinic source. Review it and explain what its contents, including the absence of SOUTH, mean for each office.

**Simulated contact information, when requested:** At 2026-11-03 09:00 -05:00, a phone call to the NORTH office received no answer. At 2026-11-03 10:00 -05:00, a second phone call reached the office manager, who reported the NORTH phone as `6175550199`. These are fictional assertions for this exercise.

**Simulated downstream information, when requested:** A fictional directory listing later observed at NORTH still shows `6175550100`. Any submission reference you use is simulated. Explain how the reported, proposed, submitted and observed values relate to one another.

## Observer reference — do not show before or during the task

Allow the participant to choose and explain actions; offer setup help only and record it. Give the later file and synthetic information above when requested, or if the participant explicitly cannot proceed without the next input. Do not supply a proposal, acceptance decision, action sequence or interpretation. The task is complete when the participant indicates they are finished; capture partial progress as such.

The initial workbook contains two valid office rows and one quarantined malformed row. NORTH's initial listed and requested phones differ; SOUTH is a separate office. The later file contains NORTH with listed phone `6175550177`, and no SOUTH row. It is a bounded later delivery: absence does not establish termination or close SOUTH. Compare with the retained initial evidence. The office-reported number is a local assertion and does not itself approve a correction or verify a directory listing. An approved proposal, simulated submission and separately observed listing are distinct events. If the participant submits a proposal different from the observed number and records that observation as verification, the case reopens; do not require them to choose that proposal. Inspect the selected case's JSON/XLSX handoff for the actual decisions and evidence, rather than presuming a particular result.

The participant may choose not to accept, submit or verify. Record their reasoning and what was observable; do not mark a decision wrong solely because it differs from the scripted engineering rehearsal. A human test remains pending until an actual participant is observed.

## Observation template

Keep identifiable participant information outside the repository. Use a dated, private receipt; leave fields unknown when not observed.

```text
Date / application revision / synthetic root identifier:
Participant pseudonym or role (optional):
Task and inputs provided / when each was provided:
Start and finish times (only if observed):
Actions and outcomes, in order:
Participant's explanation of NORTH evidence and uncertainty:
Participant's explanation of SOUTH omission:
Reported / proposed / submitted / observed distinctions:
Handoff produced and inspected (format and content):
Errors, confusing controls, unexpected behavior (exact context):
Help requested or given and its effect:
Completed / partially completed / stopped; participant's stated next action:
Observer interpretation and open questions (separate from observations):
```

After the session, select at most one evidenced problem and write its behavior, contracts, boundaries and acceptance cases in [NEXT](../NEXT.md) before implementing a change. A single observed session does not establish population-wide usability or time savings.
