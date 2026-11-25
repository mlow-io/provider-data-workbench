import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProviderDirectoryPage } from "./ProviderDirectoryPage";

function renderDirectory() {
  window.history.replaceState(null, "", "/?view=directory&demo=1");
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProviderDirectoryPage />
    </QueryClientProvider>
  );
}

describe("ProviderDirectoryPage", () => {
  it("renders Middle Tennessee clinicians with CMS Luhn badges and navigates to open issues", async () => {
    renderDirectory();

    expect(await screen.findByText(/Directory Listings \(15\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Dr\. Elena Morales, MD/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Luhn Valid").length).toBe(15);
    expect(screen.getAllByText("Directory Suppressed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Hospital-Based newpt")).toBeInTheDocument();
    expect(screen.getByText("Out-of-state license · PSV Required")).toBeInTheDocument();
    expect(screen.getAllByText(/Medicaid \/ TennCare MCO/i).length).toBeGreaterThanOrEqual(1);

    const search = screen.getByLabelText("Search directory");
    fireEvent.change(search, { target: { value: "Morales" } });

    await waitFor(() => {
      expect(screen.queryByText(/Dr\. Samuel Okafor/i)).not.toBeInTheDocument();
    });

    const issueButtons = screen.getAllByRole("button", { name: /1 Open Issue/i });
    fireEvent.click(issueButtons[0]);
    await waitFor(() => {
      expect(window.location.search).toContain("view=work");
      expect(window.location.search).toContain("case=");
      expect(window.location.search).toContain("demo=1");
    });
  });
});
