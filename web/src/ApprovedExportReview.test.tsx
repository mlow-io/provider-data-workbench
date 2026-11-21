import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ApprovedExportReview } from "./ApprovedExportReview";
afterEach(() => vi.unstubAllGlobals());
test("previews approved scope and rejects a workbook when its issue snapshot changes", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("format=xlsx")
    ? { detail: "Export snapshot changed. Refresh preview." }
    : { version_id: "v1", snapshot_id: "snapshot-one", snapshot_at: "2026-11-21T12:00:00Z", counts: { directory: 2, unresolved_issues: 1, sources: 2, quarantined_rows: 0, excluded_cross_scope_cases: 1 }, scope_notice: "Issues from another dataset scope are excluded.", directory: [{ location_id: "NORTH", phone: "2125550101" }] }), { status: url.includes("format=xlsx") ? 409 : 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<ApprovedExportReview versionId="v1" />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Preview approved workbook" }));
  await screen.findByText(/Open issues as of/);
  expect(fetcher.mock.calls[0][0]).toContain("review-preview?limit=5");
  expect(screen.getByText(/download includes all 2 approved directory rows/)).toBeVisible();
  expect(screen.getByText("Unresolved issues")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("1 cross-scope case excluded");
  expect(screen.getByRole("status")).toHaveTextContent("another dataset scope");
  fireEvent.click(screen.getByRole("button", { name: "Download reviewed workbook XLSX" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Export snapshot changed");
  expect(screen.queryByRole("button", { name: "Download reviewed workbook XLSX" })).not.toBeInTheDocument();
  expect(fetcher.mock.calls[1][0]).toContain("expected_snapshot=snapshot-one");
});

test("changing selected version invalidates a pending preview and its error state", async () => {
  let resolveOld: (response: Response) => void = () => {};
  const fetcher = vi.fn(() => new Promise<Response>(resolve => { resolveOld = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<ApprovedExportReview versionId="old" />);
  fireEvent.click(screen.getByRole("button", { name: "Preview approved workbook" }));
  view.rerender(<ApprovedExportReview versionId="new" />);
  resolveOld(new Response(JSON.stringify({ version_id: "old", snapshot_id: "old", snapshot_at: "old", counts: { directory: 999, unresolved_issues: 999, sources: 999, quarantined_rows: 999 }, directory: [] })));
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(screen.queryByText("999")).not.toBeInTheDocument();
  expect(screen.queryByText(/Open issues as of/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Preview approved workbook" })).toBeEnabled();
});
