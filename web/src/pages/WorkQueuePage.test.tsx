import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { dataClient, RequestRejected } from "@/lib/dataClient";
import { WorkQueuePage } from "./WorkQueuePage";

function renderWorkQueue() {
  window.history.replaceState(null, "", "/?demo=1");
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkQueuePage />
    </QueryClientProvider>
  );
}

describe("WorkQueuePage", () => {
  it("displays KPI summary cards and Cumberland clinic discrepancy rows", async () => {
    renderWorkQueue();

    expect(await screen.findByText("Listings without open issues")).toBeInTheDocument();
    expect(screen.getByText("Open Discrepancies")).toBeInTheDocument();
    expect(screen.getByText("Held Deliveries")).toBeInTheDocument();
    expect(screen.getByText("NSA 2-Day SLA At-Risk")).toBeInTheDocument();

    expect(await screen.findByText(/Dr\. Elena Morales, MD/i)).toBeInTheDocument();
    expect(screen.getByText(/Dr\. Rachel Alvarez, MD/i)).toBeInTheDocument();
  });

  it("filters rows by search and opens the case inspector sheet to record a triage decision", async () => {
    renderWorkQueue();

    const search = await screen.findByLabelText("Search work queue");
    fireEvent.change(search, { target: { value: "Morales" } });

    await waitFor(() => {
      expect(screen.getByText(/Dr\. Elena Morales, MD/i)).toBeInTheDocument();
      expect(screen.queryByText(/Dr\. Rachel Alvarez, MD/i)).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Inspect Dr\. Elena Morales/i }));

    expect(await screen.findByText(/Directory at intake \(phone\)/i)).toBeInTheDocument();
    expect(screen.getByText("Submitted / Reference Value")).toBeInTheDocument();
    expect(screen.getByText("(615) 555-0101")).toBeInTheDocument();
    expect(screen.getByText("(615) 555-0142")).toBeInTheDocument();
    expect(
      screen.getByText(/Phone Conflict Triage: Same Clinic Prefix \(NPA-NXX\)/i)
    ).toBeInTheDocument();
    expect(screen.getByText("LEIE unchecked")).toBeInTheDocument();
    expect(screen.getByText("Provider evidence")).toBeInTheDocument();
    expect(screen.getAllByText(/PSV Required/i).length).toBeGreaterThanOrEqual(1);

    fireEvent.change(screen.getByLabelText("Audit Rationale"), {
      target: { value: "Verified West End suite direct scheduling desk number." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Open focused workspace" }));
    expect(screen.getByLabelText("Audit Rationale")).toHaveValue("Verified West End suite direct scheduling desk number.");
    expect(screen.getByRole("button", { name: "Quick inspector" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Record Decision/i }));

    await waitFor(() => {
      expect(screen.getByText(/Audit Timeline \(1\)/i)).toBeInTheDocument();
    });
  });
  it("offers a refresh when a decision is rejected because the case changed", async () => {
    const rejectDecision = vi.spyOn(dataClient, "recordCaseEvent").mockRejectedValueOnce(new RequestRejected("Stale version", 409));
    try {
      renderWorkQueue();
      fireEvent.click(await screen.findByRole("button", { name: /Inspect Dr\. Elena Morales/i }));
      fireEvent.click(await screen.findByRole("button", { name: /Record Decision/i }));
      expect(await screen.findByText(/This case may have changed/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Record Decision/i })).toBeDisabled();
      fireEvent.click(screen.getByRole("button", { name: "Refresh case" }));
      await waitFor(() => expect(screen.getByRole("button", { name: /Record Decision/i })).toBeEnabled());
    } finally {
      rejectDecision.mockRestore();
    }
  });
  it("reopens a submitted phone correction when the later directory still shows the old phone", async () => {
    window.history.replaceState(null, "", "/?demo=1");
    const item = (await dataClient.workQueue()).find((row) => row.status === "pending_verification" && row.field_name === "phone")!;
    const row = await dataClient.caseDetail(item.id);
    const result = await dataClient.recordCaseEvent(item.id, {
      action: "verify",
      actor: "Demo Reviewer",
      reason: "Checked the latest synthetic directory",
      expected_version: row.version,
      observed: row.listing_value!,
      verification_note: "Original number still listed",
    });
    expect(result.status).toBe("reopened");
    expect(result.proposal).toBe(row.proposal);
    expect(result.history.at(-1)?.payload.observed).toBe(row.listing_value);
  });

});
