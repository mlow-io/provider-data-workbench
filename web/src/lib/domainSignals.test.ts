import { describe, expect, it } from "vitest";
import {
  buildFourGateEvidence,
  classifyPhoneConflict,
  classifyRegulatoryRegimes,
  isHospitalBasedTaxonomy,
  isAcceptingPanel,
} from "./domainSignals";

describe("domainSignals", () => {
  it("classifies regulatory regimes and hospital-based taxonomies without guessing", () => {
    expect(isHospitalBasedTaxonomy("207P00000X · Emergency Medicine")).toBe(true);
    expect(isHospitalBasedTaxonomy("207Q00000X · Family Medicine")).toBe(false);

    const regimes = classifyRegulatoryRegimes(["Volunteer Commercial PPO", "TennCare Community Plan"]);
    expect(regimes.map((r) => r.regime)).toEqual(["commercial_nsa", "medicaid_mco"]);
  });

  it("classifies phone conflict root causes accurately", () => {
    expect(classifyPhoneConflict("(615) 555-0101", "6155550142").category).toBe("same_npa_nxx_clinic_pbx");
    expect(classifyPhoneConflict("800-555-0199", "6155550142").category).toBe("toll_free_centralized_line");
    expect(classifyPhoneConflict("6155550101", "2705550101").category).toBe("different_area_code_or_state");
  });

  it("keeps unscreened providers and unchecked addresses unknown", () => {
    expect(isAcceptingPanel("")).toBeNull();
    expect(isAcceptingPanel("pending")).toBeNull();
    expect(isAcceptingPanel(false)).toBe(false);
    expect(isAcceptingPanel("newpt")).toBe(true);
    const params = { npi: "1990001012", npiLuhnValid: true };
    const evidence = buildFourGateEvidence(params);
    expect(evidence.gate1_identity.status).toBe("checksum_valid");
    expect(evidence.gate3_enrollment).toMatchObject({ status: "unverified", leie_clear: null });
    expect(evidence.gate4_directory).toMatchObject({ address_confirmed: null, accepting_new_patients: null, label: "Address unchecked" });
    expect(buildFourGateEvidence({ ...params, leieClear: false }).gate3_enrollment.leie_clear).toBe(false);
  });

  it("never promotes self-reported license state to PSV verified", () => {
    const outOfState = buildFourGateEvidence({
      npi: "1990001012",
      npiLuhnValid: true,
      practiceState: "TN",
      licenseState: "KY",
      psvVerified: false,
    });
    expect(outOfState.gate2_licensure.status).toBe("out_of_state_license_only_unverified_psv");
    expect(outOfState.gate2_licensure.psv_required).toBe(true);
  });
});
