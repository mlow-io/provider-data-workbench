# 3-Minute Demo Walkthrough

This walkthrough uses the pre-loaded **Cumberland Valley Medical Group** synthetic Middle Tennessee dataset (12 clinicians, 5 Nashville-area clinics, strictly synthetic NPIs and `(615) 555-01xx` phone numbers).

## Option A — Live local app (Python + React)

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev,intake]'
npm ci --prefix web
make workbench
```

Open the printed URL (`http://127.0.0.1:5173/`).

## Option B — Static interactive demo (zero backend required)

```sh
npm ci --prefix web
npm run build:demo --prefix web
npx --prefix web vite preview --outDir dist-demo
```

The static build runs entirely in-browser against the same Middle Tennessee showcase state, supporting live triage, schema-variant inspection, feed approval, and real JSON/CSV downloads, with a **Reset Demo** button in the top bar.

## One office phone correction

1. In **Work Queue**, open **Dr. Elena Morales** at **Nashville Midtown Clinic**. The captured clinic row shows the listed number **(615) 555-0101** and the submitted reference **(615) 555-0142**. Open **Source Evidence** for the row locator and receipt.
2. In **Review & Decide**, record triage and approve **(615) 555-0142**. Choose **Record Payer Submission** and enter the synthetic reference `DEMO-NASH-0142`.
3. Choose **Verify Observed Payer Directory** and enter **(615) 555-0101** with the note “Synthetic follow-up snapshot still lists the original phone.” The case reopens. The submission reference stays visible, payer acknowledgment is unrecorded, and the latest directory check shows **Discrepancy remains**.
4. Choose **Assign / Set Follow-Up**, assign **Directory Operations**, and set a follow-up date. The inspector shows the owner and date. **Audit Timeline** shows each decision. For a completed example, filter the queue to **All** and open **Dr. Samuel Okafor** at **Brentwood Maryland Farms**.

[See the reopened case with follow-up](images/discrepancy-inspector.png)

## What to click through

1. **Work Queue (`/`):**
   - Review the top KPI strip: **Listings without open issues**, **5 Open Discrepancies**, **1 Held Delivery**, and **NSA 2-Day SLA At-Risk**.
   - Click **Dr. Elena Morales, MD** (`Nashville Midtown Clinic`) to open the right-hand Inspector Sheet.
   - Inspect the side-by-side field diff (`(615) 555-0101` listed vs `(615) 555-0142` clinic submission), switch to **Audit Timeline** on **Dr. Samuel Okafor, MD** to see a complete 6-step verified correction, and triage a case in **Review & Decide**.
2. **Import & Adapt:**
   - Click **Renamed Payer Delta (Exclusion Flag Trap)** to load a CSV where `Clinician_NPI`, `Clinic_Code`, and `Dir_Exclude_Flag = Y` replace standard headers.
   - See `provider-network-intake` flag the unknown schema and call out that `Dir_Exclude_Flag = Y` must invert to `directory_visible = false` (never inferring network termination).
   - Preview the normalized rows (including a quarantined invalid-checksum NPI), save the reviewed variant to the catalog, and re-run **Cumberland Monthly Roster (Known Variant)** to watch deterministic recognition run with zero AI calls.
3. **Phone Corrections:**
   - Dr. Samuel Okafor practices at two offices. The approved clinic roster lists `(615) 555-0103` at **Brentwood Maryland Farms**; the Volunteer payer directory lists `(615) 555-0139`. Nashville sources agree, so that office needs nothing.
   - Choose the payer phone for Brentwood, give a reason and **Record phone decision**. The roster is unchanged.
   - **Create roster candidate** copies the complete approved roster and changes only Okafor's Brentwood row. The Nashville row stays as it was.
   - **Review and approve** opens the candidate in Deliveries with its correction lineage. Approval is a separate step that rechecks every pinned input; until then `v1` stays live.
4. **Deliveries & Export:**
   - Compare **`v2` (Held Candidate)** against **`v1` (Approved · Active)**. Notice why `v2` is held: the incoming delivery dropped **Franklin Cool Springs Clinic (`FRNK-WEST`)** and included one malformed row, so `v1` stays live for downstream consumers.
   - Click **Export Approved Roster** on `v1`, toggle between **Entire Network (15 listings)** and **Single Clinic (`NASH-MAIN`)**, preview exact counts, and download the snapshot-pinned file.
5. **Provider Directory:**
   - Search across Nashville, Franklin, Brentwood, Murfreesboro, and Hendersonville clinics, verify green **Luhn Valid** NPI badges, and jump directly from an open-issue badge back to its Work Queue case.
