import type { PortalDestination } from "@/api/types/api.types";

/**
 * Create-from-template missing-connector detection (task 17.4 / Requirement
 * 17.8).
 *
 * A Template captures each Destination's `connectorId` verbatim. When a Portal
 * is created from a Template, the seeded destinations keep that `connectorId`
 * even though the connector it references may not exist in the current
 * environment (templates can be authored in a different account/region, or the
 * connector may have been deleted since). This helper finds those orphaned
 * destinations so the editor can surface a non-blocking warning prompting the
 * administrator to reselect a connector before saving.
 *
 * Purity / snapshot safety
 * ------------------------
 * This function is pure and NON-MUTATING. It reads `destinations` and
 * `connectorIds` and returns a new array referencing the SAME destination
 * objects; it never writes to the destinations, clears a `connectorId`, or
 * otherwise touches the seeded snapshot. The copy-on-create snapshot semantics
 * (Property 11) therefore stay intact — the warning is purely informational.
 *
 * @param destinations The seeded portal destinations (each carrying its
 *   original `connectorId`). `null`/`undefined` is treated as an empty list.
 * @param connectorIds The ids of the connectors that currently exist. Accepts
 *   any iterable (array, Set, ...). `null`/`undefined` is treated as "no
 *   connectors available".
 * @returns The subset of `destinations` whose `connectorId` is absent from the
 *   current connector list. A destination with an empty/missing `connectorId`
 *   is also returned (it likewise needs a connector selected before save).
 */
export const findMissingConnectorDestinations = (
  destinations: readonly PortalDestination[] | null | undefined,
  connectorIds: Iterable<string> | null | undefined
): PortalDestination[] => {
  if (!destinations || destinations.length === 0) return [];

  const available = new Set<string>(connectorIds ?? []);

  return destinations.filter((destination) => {
    const connectorId = destination?.connectorId;
    // An empty or absent connectorId can never match a real connector, so it
    // is reported as "missing" — the admin is prompted to pick one.
    if (!connectorId) return true;
    return !available.has(connectorId);
  });
};

/**
 * Convenience label resolver for the warning copy: prefer the destination's
 * friendly name, falling back to a stable 1-based positional label when the
 * friendly name is blank. Kept alongside the detector so the warning UI and
 * its tests share one definition of how a destination is named.
 */
export const describeDestination = (
  destination: Pick<PortalDestination, "friendlyName">,
  index: number
): string => {
  const name = destination?.friendlyName?.trim();
  return name && name.length > 0 ? name : `Destination ${index + 1}`;
};
