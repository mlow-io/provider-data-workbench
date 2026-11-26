import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
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

    expect(await screen.findByText("Directory Clean Rate")).toBeInTheDocument();
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

    expect(await screen.findByText(/Current Directory \(phone\)/i)).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: /Record Decision/i }));

    await waitFor(() => {
      expect(screen.getByText(/Audit Timeline \(1\)/i)).toBeInTheDocument();
    });
  });
});
