import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, vi, test, expect } from "vitest";
import { FieldMaterialization } from "./FieldMaterialization";

const choice = { clinician_id: "clinician", location_id: "north", clinician_label: "Avery", location_label: "NORTH", snapshot: "snap", decision_id: "decision", decision_reason: "Confirmed office", old_value: { number: "6175550101", extension: null }, new_value: { number: "6175550199", extension: "007" }, selected_evidence: { source: "Reference", locator: "row:1" }, row_locator: "row:2" };
const page = (choices = [choice], next_offset: number | null = null) => new Response(JSON.stringify({ base_version: "base", choices, total: 21, next_offset }));
afterEach(() => { cleanup(); sessionStorage.clear(); vi.restoreAllMocks(); });

 test("pages reviewed scopes, shows complete phone and evidence, and creates without approval", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(page([], 20)).mockResolvedValueOnce(page()).mockResolvedValueOnce(new Response(JSON.stringify({ id: "candidate" })));
  const onCreated = vi.fn().mockResolvedValue(undefined);
  render(<FieldMaterialization versionId="base" actor="Reviewer" reason="Reviewed" onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  fireEvent.click(await screen.findByRole("button", { name: "Inspect more reviewed scopes" }));
  fireEvent.change(await screen.findByLabelText("Reviewed office and clinician"), { target: { value: "decision" } });
  expect(screen.getByText(/6175550101 · extension: Not supplied/)).toBeInTheDocument();
  expect(screen.getByText(/6175550199 · extension: 007/)).toBeInTheDocument();
  expect(screen.getByText(/Confirmed office/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Create roster candidate" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("candidate"));
  expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({ clinician_id: "clinician", location_id: "north", snapshot: "snap", decision_id: "decision", actor: "Reviewer", reason: "Reviewed", idempotency_key: expect.any(String) });
  expect(fetchMock.mock.calls[1][0]).toContain("offset=20");
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test("failed refresh removes old choices and attribution explains disabled action", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(page()).mockRejectedValueOnce(new Error("Offline"));
  render(<FieldMaterialization versionId="base" actor=" " reason="" onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  fireEvent.change(await screen.findByLabelText("Reviewed office and clinician"), { target: { value: "decision" } });
  expect(screen.getByRole("button", { name: "Create roster candidate" })).toBeDisabled();
  expect(screen.getByText(/Enter a reviewer and decision reason/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Offline");
  expect(screen.queryByLabelText("Reviewed office and clinician")).not.toBeInTheDocument();
});

test("uncertain request survives remount and retries exact payload even after attribution changes", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(page()).mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce(new Response(JSON.stringify({ id: "candidate" })));
  const onCreated = vi.fn().mockResolvedValue(undefined);
  const view = render(<FieldMaterialization versionId="base" actor="First" reason="Reason" onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  fireEvent.change(await screen.findByLabelText("Reviewed office and clinician"), { target: { value: "decision" } });
  fireEvent.click(screen.getByRole("button", { name: "Create roster candidate" }));
  await screen.findByRole("button", { name: "Retry same candidate request" });
  view.unmount();
  render(<FieldMaterialization versionId="base" actor="Changed" reason="Changed" onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("button", { name: "Retry same candidate request" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("candidate"));
  expect(fetchMock.mock.calls[1][1]?.body).toEqual(fetchMock.mock.calls[2][1]?.body);
});

test("conflict discards stale selection and requires fresh inspection", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(page()).mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Snapshot changed" }), { status: 409 }));
  render(<FieldMaterialization versionId="base" actor="Reviewer" reason="Reason" onCreated={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  fireEvent.change(await screen.findByLabelText("Reviewed office and clinician"), { target: { value: "decision" } });
  fireEvent.click(screen.getByRole("button", { name: "Create roster candidate" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Snapshot changed");
  expect(screen.queryByLabelText("Reviewed office and clinician")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry same candidate request" })).not.toBeInTheDocument();
});

test("storage denial retains the in-memory retry and cannot mask a successful candidate", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(page()).mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValueOnce(new Response(JSON.stringify({ id: "candidate" })));
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Denied"); });
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("Denied"); });
  const onCreated = vi.fn().mockResolvedValue(undefined);
  render(<FieldMaterialization versionId="base" actor="Reviewer" reason="Reason" onCreated={onCreated} />);
  fireEvent.click(screen.getByRole("button", { name: "Inspect reviewed phone decisions" }));
  fireEvent.change(await screen.findByLabelText("Reviewed office and clinician"), { target: { value: "decision" } });
  fireEvent.click(screen.getByRole("button", { name: "Create roster candidate" }));
  expect(await screen.findByText(/keep this page open and retry here/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry same candidate request" }));
  await waitFor(() => expect(onCreated).toHaveBeenCalledWith("candidate"));
  expect(fetchMock.mock.calls[1][1]?.body).toEqual(fetchMock.mock.calls[2][1]?.body);
  expect(screen.getByText(/could not clear saved retry information/)).toBeInTheDocument();
});

test("malformed saved payload is never submitted as a retry", () => {
  sessionStorage.setItem("field-materialization:base", JSON.stringify({ clinician_id: "scope", actor: "Reviewer", unexpected: "data" }));
  const fetchMock = vi.spyOn(globalThis, "fetch");
  render(<FieldMaterialization versionId="base" actor="Reviewer" reason="Reason" onCreated={vi.fn()} />);
  expect(screen.getByText(/saved retry request is invalid/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Retry same candidate request" })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
