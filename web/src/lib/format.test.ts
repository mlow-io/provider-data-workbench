import { describe, expect, it } from "vitest";
import {
  clinicDisplayName,
  daysUntilNsaCheck,
  extractLocationCode,
  formatPhone,
  formatShortDate,
  isValidNpi,
  statusLabel,
} from "./format";

describe("isValidNpi", () => {
  it("accepts CMS Luhn-valid synthetic Tennessee NPIs", () => {
    expect(isValidNpi("1990001012")).toBe(true);
    expect(isValidNpi("1990001020")).toBe(true);
    expect(isValidNpi("1990001129")).toBe(true);
  });

  it("rejects bad check digits and non-10-digit strings", () => {
    expect(isValidNpi("1234567890")).toBe(false);
    expect(isValidNpi("1990001013")).toBe(false);
    expect(isValidNpi("199000101")).toBe(false);
    expect(isValidNpi("")).toBe(false);
    expect(isValidNpi(null)).toBe(false);
  });
});

describe("format utilities", () => {
  it("formats 10-digit and 11-digit phone numbers with optional extension", () => {
    expect(formatPhone("6155550142")).toBe("(615) 555-0142");
    expect(formatPhone("1-615-555-0101", "204")).toBe("(615) 555-0101 ext. 204");
    expect(formatPhone("")).toBe("Not supplied");
  });

  it("extracts clinic codes and resolves display names", () => {
    expect(extractLocationCode("cumberland-clinic:NASH-MAIN")).toBe("NASH-MAIN");
    expect(clinicDisplayName("cumberland-clinic:NASH-MAIN")).toBe("Nashville Midtown Clinic");
    expect(clinicDisplayName("FRNK-WEST")).toBe("Franklin Cool Springs Clinic");
  });

  it("formats UTC short dates, status labels, and NSA 90-day checks", () => {
    expect(formatShortDate("2026-11-16")).toBe("Nov 16, 2026");
    expect(statusLabel("pending_verification")).toBe("Awaiting Verification");
    expect(daysUntilNsaCheck(new Date().toISOString()).compliant).toBe(true);
    expect(daysUntilNsaCheck("2020-01-01").compliant).toBe(false);
  });
});
