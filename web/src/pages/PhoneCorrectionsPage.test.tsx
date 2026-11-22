import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/App";
import { dataClient } from "@/lib/dataClient";

function renderApp(path: string) {
  window.history.replaceState(null, "", path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

describe("PhoneCorrectionsPage", () => {
  beforeEach(() => window.history.replaceState(null, "", "/?demo=1"));

  it("records a decision, creates a candidate, and approves it separately in Deliveries", async () => {
    renderApp("/?view=corrections&demo=1");

    // The office where sources disagree is selected first; the agreeing office stays separate.
    expect(await screen.findByRole("heading", { name: /Reviewed Phone Corrections/i })).toBeInTheDocument();
    const scopeList = (await screen.findByText("Reviewed office scopes")).closest("[data-slot=card]") as HTMLElement;
    expect(within(scopeList).getByText("Sources disagree")).toBeInTheDocument();
    expect(within(scopeList).getByText("Sources agree")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: /\(615\) 555-0139/ }));
    const record = screen.getByRole("button", { name: /Record phone decision/i });
    expect(record).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Decision reason/i), {
      target: { value: "Payer directory matches the office manager's confirmation" },
    });
    fireEvent.click(record);

    const create = await screen.findByRole("button", { name: /Create roster candidate/i });
    expect(screen.getByText(/Approved roster \(row:/)).toBeInTheDocument();
    expect(screen.getByText("Candidate value").nextElementSibling).toHaveTextContent("(615) 555-0139");
    fireEvent.click(create);

    const open = await screen.findByRole("button", { name: /Review and approve/i });
    expect((await dataClient.feeds())[0].current_version).toBe("ver-2026-11-02");
    expect((await dataClient.overview()).held_deliveries).toBe(1);
    fireEvent.click(open);

    expect(await screen.findByText(/Correction lineage/i)).toBeInTheDocument();
    expect(screen.getByText(/Candidate Awaiting Approval/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Approve & Promote Version/i }));

    await waitFor(async () => {
      const feed = (await dataClient.feeds())[0];
      expect(feed.current_version).not.toBe("ver-2026-11-02");
    });
    const preview = await dataClient.previewFeedExport((await dataClient.feeds())[0].current_version!);
    expect(preview.reviewed_corrections_count).toBe(1);
  });

  it("refuses a stale decision instead of overwriting a newer one", async () => {
    const [scope] = (await dataClient.phoneReviews()).filter((s) => !s.sources_agree);
    const payer = scope.options.find((o) => !o.from_approved_roster)!;
    await dataClient.decidePhone({ scope, selectedRef: payer.ref, requestId: "r1", actor: "A", reason: "first" });
    await expect(
      dataClient.decidePhone({ scope, selectedRef: payer.ref, requestId: "r2", actor: "B", reason: "stale" })
    ).rejects.toThrow(/snapshot changed/);
    // Retrying the original request is a no-op, not a second decision.
    await dataClient.decidePhone({ scope, selectedRef: payer.ref, requestId: "r1", actor: "A", reason: "first" });
    const [after] = (await dataClient.phoneReviews()).filter((s) => !s.sources_agree);
    expect(after.decision?.actor).toBe("A");
  });

  it("blocks approving the older held delivery once a correction is live", async () => {
    const [scope] = (await dataClient.phoneReviews()).filter((s) => !s.sources_agree);
    const payer = scope.options.find((o) => !o.from_approved_roster)!;
    await dataClient.decidePhone({ scope, selectedRef: payer.ref, requestId: "r1", actor: "A", reason: "r" });
    const [decided] = (await dataClient.phoneReviews()).filter((s) => !s.sources_agree);
    const candidate = await dataClient.createPhoneCandidate({ scope: decided, idempotencyKey: "k1", actor: "A", reason: "r" });
    expect((await dataClient.createPhoneCandidate({ scope: decided, idempotencyKey: "k1", actor: "A", reason: "r" })).id).toBe(candidate.id);
    await dataClient.decideFeedVersion({
      versionId: candidate.id, decision: "approved", expectedReport: candidate.report_hash,
      expectedCurrent: "ver-2026-11-02", actor: "O", reason: "ok",
    });
    const held = await dataClient.feedVersion("ver-2026-11-16");
    for (const finding of held.report.findings.filter((f) => f.severity === "hold")) {
      await dataClient.acknowledgeHold({ versionId: held.id, code: finding.code, expectedReport: held.report_hash, actor: "O", reason: "r" });
    }
    await expect(
      dataClient.decideFeedVersion({
        versionId: held.id, decision: "approved", expectedReport: held.report_hash,
        expectedCurrent: candidate.id, actor: "O", reason: "ok",
      })
    ).rejects.toThrow(/reprocess before approval/);
  });
});
