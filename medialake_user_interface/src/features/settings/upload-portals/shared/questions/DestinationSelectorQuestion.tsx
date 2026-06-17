import React, { useCallback, useEffect, useMemo } from "react";

import PortalDestinationSelector from "@/features/portal/components/PortalDestinationSelector";

import { SELECTED_DESTINATION_KEY, usePortalRuntime } from "../PortalRuntimeContext";
import {
  destinationsForPage,
  getQuestionPageNumber,
  useSurveyValue,
  type PortalQuestionRendererProps,
} from "./questionHelpers";

/**
 * React renderer for the `portal-destination-selector` custom question.
 *
 * Wraps the existing {@link PortalDestinationSelector}. The chosen
 * `destinationId` is the cross-page upload state, so it is written into the
 * reserved survey key {@link SELECTED_DESTINATION_KEY} (`__selectedDestinationId`)
 * — NOT under the question's own `name` — and `runtime.onDestinationChange` is
 * invoked so the path questions can resolve the initial prefix.
 *
 * Behaviour (Requirements 7.3, 7.4):
 *   - The picker offers only the destinations whose `pageNumber` matches the
 *     page this question is on (derived from the SurveyJS page name `page-{n}`
 *     that {@link buildSurveyJson} assigns). Portals saved before multi-page
 *     support carry no `pageNumber`, so in that case all destinations are
 *     offered (see {@link destinationsForPage}).
 *   - When a page offers exactly ONE destination, it is auto-selected (its
 *     `destinationId` written into the reserved key) WITHOUT rendering a picker.
 *   - In `preview` mode the selector is rendered non-interactively (disabled);
 *     no live API call is made here — the destination change is purely local
 *     survey state.
 */
function DestinationSelectorRenderer({
  question,
}: PortalQuestionRendererProps): React.JSX.Element | null {
  const runtime = usePortalRuntime();
  const survey = question?.survey ?? null;
  const pageNumber = getQuestionPageNumber(question);

  // Destinations offered by THIS page's selector.
  const destinations = useMemo(
    () => destinationsForPage(runtime.config, pageNumber),
    [runtime.config, pageNumber]
  );

  // Current selection, read reactively from the reserved survey key so the
  // picker reflects changes made elsewhere (e.g. an auto-select).
  const selectedDestinationId = useSurveyValue<string>(survey, SELECTED_DESTINATION_KEY) ?? "";

  const applySelection = useCallback(
    (destinationId: string) => {
      survey?.setValue(SELECTED_DESTINATION_KEY, destinationId);
      runtime.onDestinationChange?.(destinationId);
    },
    [survey, runtime]
  );

  // Auto-select when the page offers exactly one destination (Requirement 7.4).
  // Only write when the reserved key does not already hold that id, so this
  // does not loop on the resulting value-changed notification.
  const soleDestinationId = destinations.length === 1 ? destinations[0].destinationId : null;

  useEffect(() => {
    if (soleDestinationId && selectedDestinationId !== soleDestinationId) {
      applySelection(soleDestinationId);
    }
  }, [soleDestinationId, selectedDestinationId, applySelection]);

  // Nothing to choose, or a single destination was auto-selected: render no
  // picker (Requirement 7.4).
  if (destinations.length <= 1) return null;

  return (
    <PortalDestinationSelector
      destinations={destinations}
      selectedDestinationId={selectedDestinationId}
      onChange={applySelection}
      disabled={runtime.mode === "preview"}
    />
  );
}

export default DestinationSelectorRenderer;
