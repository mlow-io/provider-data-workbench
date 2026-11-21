import { render, screen, within } from "@testing-library/react";
import { DeliveryReviewSummary } from "./DeliveryReviewSummary";

test("delivery evidence preserves null, absent and empty values without implying reviewed identities", () => {
  render(<DeliveryReviewSummary baselineVersion="approved-original" comparison={{
    changed: 1, missing_from_this_delivery: 1, entry_count: 81,
    entries: [{ key: "001-NORTH", status: "changed", interpretation_changed: true, old: {}, new: {}, fields: [
      { field: "phone", old: null, new: "" },
      { field: "suite", old: null, new: "002", old_present: false, new_present: true },
      { field: "license", old: null, new: null, old_present: false, new_present: true },
    ] }],
  }} />);
  expect(screen.getByText("approved-original")).toBeVisible();
  expect(screen.getByText(/Showing 1 of 81 comparison entries/)).toBeVisible();
  const row = screen.getByRole("row", { name: /001-NORTH/ });
  expect(within(row).getByText("Before: Null")).toBeVisible();
  expect(within(row).getByText("After: Empty text")).toBeVisible();
  expect(within(row).getAllByText("Before: Not supplied")).toHaveLength(2);
  expect(within(row).getByText("After: 002")).toBeVisible();
  expect(within(row).getByText("After: Null")).toBeVisible();
  expect(screen.getByText(/Interpretation rules changed/)).toBeVisible();
  expect(screen.getAllByText("Not assessed")).toHaveLength(4);
  expect(screen.getByText(/not counts of reviewed clinicians or offices/)).toBeVisible();
});

test("an unavailable comparison stays unavailable rather than reporting zero changes", () => {
  render(<DeliveryReviewSummary comparison={null} />);
  expect(screen.getByText(/Comparison is unavailable/)).toBeVisible();
  expect(screen.getByText(/Baseline-dependent checks are not assessed/)).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
