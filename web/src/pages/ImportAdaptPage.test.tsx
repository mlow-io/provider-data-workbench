import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportAdaptPage } from "./ImportAdaptPage";

function renderImportAdapt() {
  window.history.replaceState(null, "", "/?view=intake&demo=1");
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ImportAdaptPage />
    </QueryClientProvider>
  );
}

describe("ImportAdaptPage", () => {
  it("loads the unfamiliar payer delta, surfaces exclusion & Luhn findings, saves a variant, and stages valid rows", async () => {
    renderImportAdapt();

    const payerDeltaBtn = await screen.findByRole("button", {
      name: /Renamed Payer Delta \(Exclusion Trap\)/i,
    });
    fireEvent.click(payerDeltaBtn);

    expect(
      await screen.findByText(/Exclusion Flag Semantics Detected:/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/1234567890/)).toBeInTheDocument();
    expect(screen.getByText("Invalid Checksum")).toBeInTheDocument();

    const saveVariantBtn = screen.getByRole("button", { name: /Save Reviewed Variant/i });
    fireEvent.click(saveVariantBtn);

    await waitFor(() => {
      expect(screen.getByText(/Saved Schema Variants \(2\)/i)).toBeInTheDocument();
    });

    const acceptBtn = screen.getByRole("button", { name: /Accept Valid Rows to Staging/i });
    fireEvent.click(acceptBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Accepted to Staging/i })).toBeDisabled();
    });
  });
});
