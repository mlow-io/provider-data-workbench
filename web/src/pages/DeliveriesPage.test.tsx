import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DeliveriesPage } from "./DeliveriesPage";

function renderDeliveries() {
  window.history.replaceState(null, "", "/?view=deliveries&demo=1");
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DeliveriesPage />
    </QueryClientProvider>
  );
}

describe("DeliveriesPage", () => {
  it("shows held v2 checks, unlocks promotion once holds are acknowledged, and previews v1 exports", async () => {
    renderDeliveries();

    expect(
      await screen.findByText(/Candidate Held Automatically — Active Approved Baseline Protected/i)
    ).toBeInTheDocument();

    const ackButtons = screen.getAllByRole("button", { name: /Acknowledge Hold/i });
    expect(ackButtons.length).toBe(3);

    const promoteBtn = screen.getByRole("button", { name: /Approve & Promote Version/i });
    expect(promoteBtn).toBeDisabled();

    for (const btn of ackButtons) {
      fireEvent.click(btn);
      await waitFor(() => {
        expect(btn).toBeDisabled();
      });
    }

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Approve & Promote Version/i })
      ).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /Nov 2, 2026 Delivery/i }));
    const exportBtn = await screen.findByRole("button", { name: /Export Approved Roster/i });
    await waitFor(() => expect(exportBtn).not.toBeDisabled());
    fireEvent.click(exportBtn);

    expect(await screen.findByText("Export Approved Directory Snapshot")).toBeInTheDocument();
    expect(await screen.findByText(/Snapshot pin:/i)).toBeInTheDocument();
  });
});
