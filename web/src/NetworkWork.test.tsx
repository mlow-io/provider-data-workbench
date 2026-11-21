import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import {
  NetworkWorkFilters,
  NetworkCaseScope,
  FollowUpCaseScopes,
  matchesWorkScope,
} from "./NetworkWork";

test("selected network downloads carry only that opaque network id", () => {
  const onNetwork = vi.fn();
  render(
    <NetworkWorkFilters
      items={[
        {
          id: "case-1",
          network_id: "cedar-id",
          network_label: "CEDAR",
          organization_id: "clinic-id",
          organization_label: "Clinic",
          practice_location_id: "north-id",
          location_label: "NORTH",
        },
        {
          id: "case-2",
          network_id: "pine-id",
          network_label: "PINE",
          organization_id: "clinic-id",
          organization_label: "Clinic",
          practice_location_id: "north-id",
          location_label: "NORTH",
        },
      ]}
      networkId="cedar-id"
      organizationId=""
      locationId=""
      onNetwork={onNetwork}
      onOrganization={() => {}}
      onLocation={() => {}}
    />,
  );
  expect(
    screen.getByRole("link", { name: "Download selected network XLSX" }),
  ).toHaveAttribute("href", "/api/work-export.xlsx?network_id=cedar-id");
  expect(
    screen.getByRole("link", { name: "Download selected network JSON" }),
  ).toHaveAttribute("href", "/api/work-export.json?network_id=cedar-id");
  expect(
    screen.getByText(/Shared receipt and attempt payloads/),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Network filter" }), {
    target: { value: "pine-id" },
  });
  expect(onNetwork).toHaveBeenCalledWith("pine-id");
});

test("participation review displays source comparison without relabeling it human verification", () => {
  render(
    <NetworkCaseScope
      scope={{
        case_id: "case-1",
        network_id: "cedar-id",
        network_label: "CEDAR",
        organization_id: "clinic-id",
        organization_label: "Clinic",
        practice_location_id: "north-id",
        location_label: "NORTH",
        native_key: "LIST-A",
      }}
      evidence={{
        normalized: {
          participation: {
            listed_status: "listed",
            effective_date: "2026-01-01",
            end_date: null,
          },
        },
      }}
      review={[
        {
          id: 1,
          status: "blocked_invalid",
          locator: "row:3",
          receipt_id: "receipt-2",
          receipt_label: "changed.csv",
          payload: {
            meaning: "Source comparison evidence only",
            comparison: {
              status: "blocked_invalid",
              old: { phone: "5550100000" },
              new: { phone: "5550100008" },
              fields: [
                { field: "phone", old: "5550100000", new: "5550100008" },
              ],
              previous_locator: "row:2",
              current_locator: "row:3",
              previous_receipt_id: "receipt-1",
            },
            source_row: { problems: ["effective_date must use YYYY-MM-DD"] },
          },
        },
      ]}
    />,
  );
  expect(
    screen.getByText(/Source-listed status and dates are source assertions/),
  ).toBeInTheDocument();
  expect(screen.getByText("5550100008")).toBeInTheDocument();
  expect(
    screen.getByText(/effective_date must use YYYY-MM-DD/),
  ).toBeInTheDocument();
  expect(screen.getByText(/baseline receipt/)).toBeInTheDocument();
});

test("follow-up scope supplies filter choices without fabricating participation labels", () => {
  const onNetwork = vi.fn();
  const scopes = [
    {
      target_key: "target-cedar",
      kind: "follow_up" as const,
      source: "payer",
      field: "phone",
      clinician_id: "clinician-one",
      clinician_label: "Alex reviewed",
      network_id: "cedar-id",
      network_label: "CEDAR",
      organization_id: "org-one",
      organization_label: "Clinic",
      practice_location_id: "north-id",
      location_label: "NORTH",
      confirmation_id: "confirmation-one",
    },
    {
      target_key: "target-pine",
      kind: "follow_up" as const,
      source: "payer",
      field: "phone",
      clinician_id: "clinician-one",
      clinician_label: "Alex reviewed",
      network_id: "pine-id",
      network_label: "PINE",
      organization_id: "org-two",
      organization_label: "Other clinic",
      practice_location_id: "south-id",
      location_label: "SOUTH",
      confirmation_id: "confirmation-two",
    },
  ];
  render(
    <NetworkWorkFilters
      items={[
        {
          id: "follow-up-case",
          network_id: null,
          practice_location_id: null,
          follow_up_scopes: scopes,
        },
      ]}
      networkId=""
      organizationId=""
      locationId=""
      onNetwork={onNetwork}
      onOrganization={() => {}}
      onLocation={() => {}}
    />,
  );
  expect(
    screen.getByRole("option", { name: "CEDAR · cedar-id" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("option", { name: "PINE · pine-id" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("option", { name: "NORTH · north-id" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("option", { name: "SOUTH · south-id" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("option", { name: "Clinic · org-one" }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Network filter" }), {
    target: { value: "cedar-id" },
  });
  expect(onNetwork).toHaveBeenCalledWith("cedar-id");
});

test("reviewed follow-up scope is displayed separately and does not imply source participation", () => {
  render(
    <>
      <NetworkCaseScope scope={null} review={[]} />
      <FollowUpCaseScopes
        scopes={[
          {
            target_key: "target-one",
            kind: "follow_up",
            source: "payer roster",
            field: "phone",
            clinician_id: "clinician-one",
            clinician_label: "Alex reviewed",
            network_id: "cedar-id",
            network_label: "CEDAR",
            organization_id: "org-one",
            organization_label: "Clinic",
            practice_location_id: "north-id",
            location_label: "NORTH",
            confirmation_id: "confirmation-one",
          },
        ]}
      />
    </>,
  );
  expect(
    screen.getByRole("region", { name: "Follow-up review scope" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("region", { name: "Network participation scope" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/Source participation, if present, is shown separately/),
  ).toBeInTheDocument();
  expect(screen.getByText("Alex reviewed · clinician-one")).toBeInTheDocument();
});

test("combined filters match one scope rather than combining unrelated follow-up associations", () => {
  const item = {
    id: "shared-case",
    follow_up_scopes: [
      {
        target_key: "one",
        kind: "follow_up" as const,
        source: "payer",
        field: "phone",
        clinician_id: "clinician-one",
        confirmation_id: "confirmation-one",
        network_id: "cedar-id",
        practice_location_id: "north-id",
      },
      {
        target_key: "two",
        kind: "follow_up" as const,
        source: "payer",
        field: "phone",
        clinician_id: "clinician-one",
        confirmation_id: "confirmation-two",
        network_id: "pine-id",
        practice_location_id: "south-id",
      },
    ],
  };
  expect(
    matchesWorkScope(item, {
      networkId: "cedar-id",
      locationId: "north-id",
      organizationId: "",
    }),
  ).toBe(true);
  expect(
    matchesWorkScope(item, {
      networkId: "cedar-id",
      locationId: "south-id",
      organizationId: "",
    }),
  ).toBe(false);
  expect(
    matchesWorkScope(
      {
        id: "old-case",
        network_id: "cedar-id",
        practice_location_id: "north-id",
      },
      { networkId: "cedar-id", locationId: "north-id", organizationId: "" },
    ),
  ).toBe(true);
});
