import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

function renderApp(initialPath = "/?demo=1") {
  window.history.replaceState(null, "", initialPath);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

describe("App shell navigation and demo controls", () => {
  it("renders only the five primary navigation destinations without legacy labels", async () => {
    renderApp("/?demo=1");

    expect(
      (await screen.findAllByRole("link", { name: /Work Queue/i })).length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("link", { name: /Import & Adapt/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Phone Corrections/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Deliveries & Export/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Provider Directory/i })).toBeInTheDocument();

    expect(screen.queryByText(/Source Mapping/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Operations Hub/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Interactive Demo · Synthetic TN/i)).toBeInTheDocument();
    expect(screen.getByText(/Static Demo Sandbox/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reset Demo/i })).toBeInTheDocument();
  });

  it("switches workspaces via sidebar links and preserves demo mode", async () => {
    renderApp("/?demo=1");

    fireEvent.click(await screen.findByRole("link", { name: /Import & Adapt/i }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Import & Schema Adaptation/i })).toBeInTheDocument();
    });
    expect(window.location.search).toContain("view=intake");
    expect(window.location.search).toContain("demo=1");

    fireEvent.click(screen.getByRole("link", { name: /Provider Directory/i }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Provider & Clinic Directory/i })).toBeInTheDocument();
    });
  });
});
