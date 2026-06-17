import React, { useCallback, useMemo } from "react";
import { Typography } from "@mui/material";

import PortalPathBuilder from "@/features/portal/components/PortalPathBuilder";

import {
  CURRENT_PATH_KEY,
  SELECTED_DESTINATION_KEY,
  usePortalRuntime,
} from "../PortalRuntimeContext";
import { useSurveyValue, type PortalQuestionRendererProps } from "./questionHelpers";

/**
 * React renderer for the `portal-path-builder` custom question.
 *
 * Wraps the existing {@link PortalPathBuilder} (regex-validated structured path
 * segments). When the builder reports a VALID path, the resolved path —
 * `rootPath + builtPath + "/"`, matching the legacy `UploadPortalPage` // i18n-ignore
 * behaviour — is written into the reserved survey key {@link CURRENT_PATH_KEY}
 * (`__currentPath`) and `runtime.onPathChange` is invoked (Requirement 7.5).
 * Invalid input does not overwrite the resolved path.
 *
 * The active destination (which carries the `pathSegments` + `pathSeparator`)
 * is read reactively from {@link SELECTED_DESTINATION_KEY}.
 *
 * Modes:
 *   - `public`: interactive; threads the resolved path through survey state.
 *   - `preview`: renders the builder for visual fidelity but is non-interactive
 *     (changes are not written to survey state and no callback fires), so the
 *     preview never mutates threaded upload state. The builder itself performs
 *     no API calls in either mode.
 */
function PathBuilderRenderer({ question }: PortalQuestionRendererProps): React.JSX.Element | null {
  const runtime = usePortalRuntime();
  const survey = question?.survey ?? null;
  const isPreview = runtime.mode === "preview";

  const selectedDestinationId = useSurveyValue<string>(survey, SELECTED_DESTINATION_KEY) ?? "";

  const destination = useMemo(
    () =>
      runtime.config?.destinations?.find((d) => d.destinationId === selectedDestinationId) ?? null,
    [runtime.config, selectedDestinationId]
  );

  const handleChange = useCallback(
    (constructedPath: string, isValid: boolean) => {
      // Preview is read-only: never thread state.
      if (isPreview) return;
      if (!isValid) return;
      const rootPath = destination?.rootPath ?? "";
      const resolved = `${rootPath}${constructedPath}/`;
      survey?.setValue(CURRENT_PATH_KEY, resolved);
      runtime.onPathChange?.(resolved);
    },
    [isPreview, destination, survey, runtime]
  );

  const segments = destination?.pathSegments ?? null;
  if (!segments || segments.length === 0) {
    if (isPreview) {
      return (
        <Typography variant="body2" color="text.secondary">
          Structured path builder (no segments configured).
        </Typography>
      );
    }
    return null;
  }

  return (
    <PortalPathBuilder
      pathSegments={segments}
      prePopulatedValues={{}}
      onChange={handleChange}
      pathSeparator={destination?.pathSeparator}
    />
  );
}

export default PathBuilderRenderer;
