import { describe, expect, it } from "vitest";

import type { PortalDestination } from "@/api/types/api.types";

import {
  describeDestination,
  findMissingConnectorDestinations,
} from "./findMissingConnectorDestinations";

/**
 * Unit tests for the create-from-template missing-connector detector
 * (task 17.4).
 *
 * **Validates: Requirements 17.8**
 *
 * Covers:
 *   - The warning path: a destination referencing a `connectorId` NOT in the
 *     current connector list is reported.
 *   - No warning when every `connectorId` is present.
 *   - Snapshot safety: the input destinations are NOT mutated and the returned
 *     entries are the SAME object references (the detector never clears a
 *     `connectorId`).
 *   - Edge cases: empty/missing inputs, empty connector list, and a
 *     destination with a blank `connectorId`.
 */

/** Build a `PortalDestination` with sensible defaults for the bits we test. */
const makeDestination = (overrides: Partial<PortalDestination>): PortalDestination => ({
  destinationId: overrides.destinationId ?? "dest-1",
  friendlyName: overrides.friendlyName ?? "Destination",
  connectorId: overrides.connectorId ?? "connector-1",
  rootPath: overrides.rootPath ?? "/",
  allowBrowsing: overrides.allowBrowsing ?? false,
  allowFolderCreation: overrides.allowFolderCreation ?? false,
  order: overrides.order ?? 0,
  ...overrides,
});

describe("findMissingConnectorDestinations", () => {
  it("reports a destination whose connectorId is absent from the connector list", () => {
    const orphan = makeDestination({
      destinationId: "dest-orphan",
      friendlyName: "Archive bucket",
      connectorId: "connector-gone",
    });
    const present = makeDestination({
      destinationId: "dest-ok",
      friendlyName: "Project assets",
      connectorId: "connector-1",
    });

    const missing = findMissingConnectorDestinations(
      [present, orphan],
      ["connector-1", "connector-2"]
    );

    expect(missing).toHaveLength(1);
    expect(missing[0]).toBe(orphan);
    expect(missing[0].friendlyName).toBe("Archive bucket");
  });

  it("returns an empty array when every connectorId is present", () => {
    const destinations = [
      makeDestination({ destinationId: "d1", connectorId: "connector-1" }),
      makeDestination({ destinationId: "d2", connectorId: "connector-2" }),
    ];

    const missing = findMissingConnectorDestinations(destinations, [
      "connector-1",
      "connector-2",
      "connector-3",
    ]);

    expect(missing).toEqual([]);
  });

  it("treats a blank or missing connectorId as missing", () => {
    const blank = makeDestination({ destinationId: "d-blank", connectorId: "" });
    const undefinedId = makeDestination({ destinationId: "d-undef" });
    // Force-remove the connectorId to simulate a malformed seed.
    delete (undefinedId as { connectorId?: string }).connectorId;

    const missing = findMissingConnectorDestinations([blank, undefinedId], ["connector-1"]);

    expect(missing).toHaveLength(2);
  });

  it("reports all destinations when the connector list is empty", () => {
    const destinations = [
      makeDestination({ destinationId: "d1", connectorId: "connector-1" }),
      makeDestination({ destinationId: "d2", connectorId: "connector-2" }),
    ];

    expect(findMissingConnectorDestinations(destinations, [])).toEqual(destinations);
    expect(findMissingConnectorDestinations(destinations, null)).toEqual(destinations);
    expect(findMissingConnectorDestinations(destinations, undefined)).toEqual(destinations);
  });

  it("returns an empty array for empty/missing destinations", () => {
    expect(findMissingConnectorDestinations([], ["connector-1"])).toEqual([]);
    expect(findMissingConnectorDestinations(null, ["connector-1"])).toEqual([]);
    expect(findMissingConnectorDestinations(undefined, ["connector-1"])).toEqual([]);
  });

  it("accepts a Set of connector ids", () => {
    const destinations = [
      makeDestination({ destinationId: "d1", connectorId: "connector-1" }),
      makeDestination({ destinationId: "d2", connectorId: "connector-x" }),
    ];

    const missing = findMissingConnectorDestinations(destinations, new Set(["connector-1"]));

    expect(missing).toHaveLength(1);
    expect(missing[0].destinationId).toBe("d2");
  });

  it("does NOT mutate the input destinations (snapshot semantics intact)", () => {
    const orphan = makeDestination({
      destinationId: "dest-orphan",
      connectorId: "connector-gone",
    });
    const before = structuredClone(orphan);

    const missing = findMissingConnectorDestinations([orphan], ["connector-1"]);

    // The reported destination is the same reference, unchanged — the detector
    // never clears `connectorId` or otherwise touches the seeded snapshot.
    expect(missing[0]).toBe(orphan);
    expect(orphan).toEqual(before);
    expect(orphan.connectorId).toBe("connector-gone");
  });
});

describe("describeDestination", () => {
  it("uses the friendly name when present", () => {
    expect(describeDestination({ friendlyName: "Main bucket" }, 0)).toBe("Main bucket");
  });

  it("falls back to a 1-based positional label when the friendly name is blank", () => {
    expect(describeDestination({ friendlyName: "" }, 0)).toBe("Destination 1");
    expect(describeDestination({ friendlyName: "   " }, 2)).toBe("Destination 3");
  });
});
