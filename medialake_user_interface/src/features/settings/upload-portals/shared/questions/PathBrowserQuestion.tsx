import React, { useCallback, useMemo, useState } from "react";
import { Box, Button, Typography } from "@mui/material";

import PortalPathBrowser from "@/features/portal/components/PortalPathBrowser";

import {
  CURRENT_PATH_KEY,
  SELECTED_DESTINATION_KEY,
  usePortalRuntime,
} from "../PortalRuntimeContext";
import { useSurveyValue, type PortalQuestionRendererProps } from "./questionHelpers";

/**
 * React renderer for the `portal-path-browser` custom question.
 *
 * Wraps the existing {@link PortalPathBrowser} dialog. The resolved S3 prefix
 * is cross-page upload state, so it is written into the reserved survey key
 * {@link CURRENT_PATH_KEY} (`__currentPath`) and `runtime.onPathChange` is
 * invoked (Requirement 7.5).
 *
 * The chosen destination is read reactively from {@link SELECTED_DESTINATION_KEY}
 * (written by the destination-selector question on an earlier page), so the
 * browser always navigates the currently selected destination.
 *
 * Modes:
 *   - `public`: renders a "Browse" trigger plus the live dialog (which performs
 *     the real `/portal/.../browse` + folder-create API calls via the existing
 *     component's hook).
 *   - `preview`: renders a non-interactive, read-only path display and never
 *     opens the dialog, so no live API call is made.
 */
function PathBrowserRenderer({ question }: PortalQuestionRendererProps): React.JSX.Element | null {
  const runtime = usePortalRuntime();
  const survey = question?.survey ?? null;
  const [open, setOpen] = useState(false);

  const selectedDestinationId = useSurveyValue<string>(survey, SELECTED_DESTINATION_KEY) ?? "";
  const currentPath = useSurveyValue<string>(survey, CURRENT_PATH_KEY) ?? "";

  const destination = useMemo(
    () =>
      runtime.config?.destinations?.find((d) => d.destinationId === selectedDestinationId) ?? null,
    [runtime.config, selectedDestinationId]
  );

  const handlePathSelect = useCallback(
    (path: string) => {
      survey?.setValue(CURRENT_PATH_KEY, path);
      runtime.onPathChange?.(path);
      setOpen(false);
    },
    [survey, runtime]
  );

  // Preview mode: read-only display, no live browse calls.
  if (runtime.mode === "preview") {
    return (
      <Box>
        <Button variant="outlined" size="small" disabled sx={{ alignSelf: "flex-start" }}>
          Browse: {currentPath || "/"}
        </Button>
      </Box>
    );
  }

  // Public mode: cannot browse until a destination has been chosen and a live
  // session exists. Render nothing rather than a dead button.
  if (!destination || !runtime.sessionJwt) {
    return (
      <Typography variant="body2" color="text.secondary">
        Select a destination to browse folders.
      </Typography>
    );
  }

  return (
    <Box>
      <Button
        variant="outlined"
        size="small"
        onClick={() => setOpen(true)}
        sx={{ alignSelf: "flex-start" }}
      >
        Browse: {currentPath || "/"}
      </Button>
      <PortalPathBrowser
        open={open}
        onClose={() => setOpen(false)}
        slug={runtime.slug}
        sessionJwt={runtime.sessionJwt}
        destination={destination}
        currentPath={currentPath}
        onPathSelect={handlePathSelect}
      />
    </Box>
  );
}

export default PathBrowserRenderer;
