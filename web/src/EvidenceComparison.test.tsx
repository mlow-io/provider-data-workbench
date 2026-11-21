import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { EvidenceComparison } from "./EvidenceComparison";

test("uses the declared mapping while preserving text identifiers and missing-value distinctions", () => {
  render(<EvidenceComparison original={{ "Office tel": "(212) 555-0101", zip: "00123", empty: "", nullable: null, extra: "retained" }} interpreted={{ phone: "2125550101", zip: "00123", empty: "", nullable: null, unknown: "unknown" }} mapping={{ phone: "Office tel" }} />);
  const table = screen.getByRole("table");
  const phone = within(table).getByRole("row", { name: /phone Office tel/ });
  expect(phone).toHaveTextContent("(212) 555-0101");
  expect(phone).toHaveTextContent("2125550101");
  expect(phone).toHaveTextContent("Changed");
  expect(within(table).getByRole("row", { name: /zip/ })).toHaveTextContent("00123");
  expect(within(table).getByRole("row", { name: /nullable/ })).toHaveTextContent("NullNullUnchanged");
  expect(within(table).getByRole("row", { name: /empty/ })).toHaveTextContent("BlankBlankUnchanged");
  expect(within(table).getByRole("row", { name: /unknown/ })).toHaveTextContent("AbsentunknownNo same-column comparison");
  expect(within(table).getByRole("row", { name: /extra/ })).toHaveTextContent("retainedAbsentSource only");
  expect(screen.getByText("Original and interpreted payloads")).toBeInTheDocument();
});

test("never guesses a source binding from a similar header", () => {
  render(<EvidenceComparison original={{ "Office phone": "111" }} interpreted={{ phone: "222" }} />);
  expect(screen.getByRole("row", { name: /^phone/ })).toHaveTextContent("No same-column comparison");
  expect(screen.getByRole("row", { name: /^Office phone/ })).toHaveTextContent("Source only");
});
