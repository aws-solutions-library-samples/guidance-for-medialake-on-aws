import React, { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import DesktopWindowsIcon from "@mui/icons-material/DesktopWindows";
import TabletMacIcon from "@mui/icons-material/TabletMac";
import PhoneIphoneIcon from "@mui/icons-material/PhoneIphone";
import LockIcon from "@mui/icons-material/Lock";
import PublicIcon from "@mui/icons-material/Public";

import { usePortalEditorStore, type PreviewMode } from "../../stores/usePortalEditorStore";
import { loadGoogleFont } from "../../utils/loadGoogleFont";
import PortalPreviewRenderer from "./PortalPreviewRenderer";
import type { PortalDestination, PortalMetadataField } from "@/api/types/api.types";

/**
 * Stable empty-array defaults. The portal editor preview reflects ONLY the
 * fields/destinations the admin has actually configured — there is no mock
 * fallback, so an unconfigured portal previews as an empty form rather than
 * showing phantom fields that don't exist in Field Configuration.
 */
const EMPTY_METADATA_FIELDS: PortalMetadataField[] = [];
const EMPTY_DESTINATIONS: PortalDestination[] = [];

/**
 * Props for {@link PortalEditorPreview}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces" exactly.
 */
export interface PortalEditorPreviewProps {
  previewMode: PreviewMode;
  onPreviewModeChange: (mode: PreviewMode) => void;
}

/**
 * Ordered device toggles rendered in the preview top bar.
 *
 * Order is locked by Requirement 11.1: Desktop, Tablet, Mobile.
 */
const DEVICE_OPTIONS: {
  key: PreviewMode;
  label: string;
  Icon: React.ComponentType<{ fontSize?: "inherit" | "small" | "medium" | "large" }>;
}[] = [
  { key: "desktop", label: "Desktop", Icon: DesktopWindowsIcon },
  { key: "tablet", label: "Tablet", Icon: TabletMacIcon },
  { key: "mobile", label: "Mobile", Icon: PhoneIphoneIcon },
];

/**
 * Widths applied to the inner preview frame per device mode. Values come
 * from the task spec (Requirement 11.2): desktop fills the available space,
 * tablet pins to 768px (the classic iPad portrait breakpoint), and mobile
 * pins to 375px (the iPhone portrait breakpoint).
 */
const PREVIEW_FRAME_WIDTHS: Record<PreviewMode, string> = {
  desktop: "100%",
  tablet: "768px",
  mobile: "375px",
};

/**
 * Checkered background CSS rendered outside the preview card. Emulates the
 * standard "transparent canvas" treatment so the card's card-style shadow
 * and background color stand out while also hinting that the surrounding
 * area is a preview chrome, not part of the portal itself
 * (Requirement 11.4).
 *
 * Implemented via two overlapping conic-style linear gradients offset by
 * half the cell size. Each gradient paints a two-tone 45° pattern; layered
 * together they produce the familiar checkerboard. 16px cells keep the
 * pattern subtle at both the desktop and mobile widths.
 */
const CHECKER_CELL_PX = 16;
const CHECKER_BACKGROUND = {
  backgroundImage: [
    `linear-gradient(45deg, rgba(0, 0, 0, 0.04) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.04) 75%)`,
    `linear-gradient(45deg, rgba(0, 0, 0, 0.04) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.04) 75%)`,
  ].join(", "),
  backgroundSize: `${CHECKER_CELL_PX * 2}px ${CHECKER_CELL_PX * 2}px`,
  backgroundPosition: `0 0, ${CHECKER_CELL_PX}px ${CHECKER_CELL_PX}px`,
} as const;

/**
 * PortalEditorPreview
 *
 * Right-hand preview panel for the portal visual editor. Subscribes to the
 * appearance + portalData slices of the editor store, applies
 * `useDeferredValue` to coalesce rapid edits (Requirement 3.8), eagerly
 * loads Google Fonts for the active heading + body families, and renders
 * the mock portal via {@link PortalPreviewRenderer} inside a responsive
 * frame.
 *
 * Accessibility (Requirement 16.1, 16.2):
 *   - The outer wrapper is a `role="region"` with
 *     `aria-label="Portal preview"` so screen reader users can jump to it
 *     via rotor navigation.
 *   - The authenticated preview renders the form interactively so admins can
 *     try the field controls before publishing; its subtree is therefore part
 *     of the accessibility tree (not `aria-hidden`). The custom questions
 *     (uploader, destination picker, path questions) stay non-functional via
 *     their runtime `mode: "preview"` branches. // i18n-ignore
 */
const PortalEditorPreview: React.FC<PortalEditorPreviewProps> = ({
  previewMode,
  onPreviewModeChange,
}) => {
  const [previewView, setPreviewView] = useState<"authenticated" | "access-gate">("authenticated");

  const handleChange = (_event: React.MouseEvent<HTMLElement>, newMode: PreviewMode | null) => {
    // MUI emits `null` when the user clicks the currently-selected button.
    // Guarding here keeps the selection non-empty per Requirement 11.1.
    if (newMode !== null) {
      onPreviewModeChange(newMode);
    }
  };

  const handleViewChange = (
    _event: React.MouseEvent<HTMLElement>,
    newView: "authenticated" | "access-gate" | null
  ) => {
    if (newView !== null) {
      setPreviewView(newView);
    }
  };

  // Subscribe to the appearance slice. The renderer memoizes the theme it
  // builds from this value, so re-renders here are cheap once the deferred
  // value stabilizes.
  const appearance = usePortalEditorStore((s) => s.appearance);

  // Access mode for the access gate preview
  const accessMode = usePortalEditorStore(
    (s) => (s.portalData?.accessMode as string | undefined) ?? "public"
  );

  // Subscribe to the fields the renderer actually needs. The selector is
  // intentionally narrow so unrelated portalData churn (e.g. slug edits)
  // doesn't invalidate the preview. Mock fallbacks keep the preview full
  // in create mode before any real metadata fields / destinations exist.
  const portalName = usePortalEditorStore((s) => s.portalData?.name);
  const portalLogoUrl = usePortalEditorStore((s) => s.portalData?.logoUrl);
  const portalLogoFile = usePortalEditorStore((s) => s.portalData?.logoFile);
  const portalMetadataFields = usePortalEditorStore((s) => s.portalData?.metadataFields);
  const portalDestinations = usePortalEditorStore((s) => s.portalData?.destinations);

  // Generate a local object-URL preview when a File is stashed so the
  // live preview shows the logo the admin just picked, even before save.
  const logoPreviewUrl = useMemo(() => {
    if (portalLogoFile instanceof File) {
      return URL.createObjectURL(portalLogoFile);
    }
    return null;
  }, [portalLogoFile]);

  useEffect(() => {
    return () => {
      if (logoPreviewUrl) {
        URL.revokeObjectURL(logoPreviewUrl);
      }
    };
  }, [logoPreviewUrl]);

  const portalData = useMemo(
    () => ({
      name: (portalName as string | undefined) ?? "Your portal",
      logoUrl: logoPreviewUrl ?? (portalLogoUrl as string | undefined),
      metadataFields:
        (portalMetadataFields as PortalMetadataField[] | undefined) ?? EMPTY_METADATA_FIELDS,
      destinations: (portalDestinations as PortalDestination[] | undefined) ?? EMPTY_DESTINATIONS,
    }),
    [
      portalName,
      portalLogoUrl,
      portalLogoFile,
      logoPreviewUrl,
      portalMetadataFields,
      portalDestinations,
    ]
  );

  // Coalesce rapid edits. React may render the preview with a stale
  // appearance while the UI thread catches up with fresher sidebar edits
  // (e.g. color-picker drag), which keeps the editor snappy even though
  // the preview subtree is comparatively expensive.
  const deferredAppearance = useDeferredValue(appearance);

  // Eagerly inject Google Fonts stylesheets when the active typography
  // families change. `loadGoogleFont` is idempotent (see Property 7), so
  // calling it with the same family repeatedly is a no-op after the first
  // load. Using the un-deferred `appearance.typography` values makes the
  // font request fire as soon as the user selects a new family — the
  // deferred preview subtree will pick the loaded font up automatically.
  useEffect(() => {
    loadGoogleFont(appearance.typography.headingFontFamily);
    loadGoogleFont(appearance.typography.bodyFontFamily);
  }, [appearance.typography.headingFontFamily, appearance.typography.bodyFontFamily]);

  const frameWidth = PREVIEW_FRAME_WIDTHS[previewMode];

  return (
    <Box
      role="region"
      aria-label="Portal preview"
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        minHeight: 0,
      }}
    >
      {/* Top bar: responsive device toggles. Not hidden from AT — admins
          may cycle through modes via keyboard. */}
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="center"
        sx={{
          height: 48,
          minHeight: 48,
          flexShrink: 0,
          px: 2,
          gap: 2,
        }}
      >
        <ToggleButtonGroup
          value={previewMode}
          exclusive
          onChange={handleChange}
          size="small"
          aria-label="Preview device"
        >
          {DEVICE_OPTIONS.map(({ key, label, Icon }) => (
            <Tooltip key={key} title={label}>
              <ToggleButton value={key} aria-label={label}>
                <Icon fontSize="small" />
              </ToggleButton>
            </Tooltip>
          ))}
        </ToggleButtonGroup>

        <ToggleButtonGroup
          value={previewView}
          exclusive
          onChange={handleViewChange}
          size="small"
          aria-label="Preview view"
        >
          <ToggleButton value="authenticated" aria-label="Authenticated view">
            Authenticated
          </ToggleButton>
          <ToggleButton value="access-gate" aria-label="Access gate view">
            Access Gate
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {/* Preview frame. Centered card with a checkered canvas behind it
          (Requirement 11.4) and vertical scrolling when the mock overflows
          the viewport (Requirement 11.5). The authenticated preview is now
          interactive (admins can try dropdowns/checkboxes/etc. before
          publishing), so this subtree is intentionally NOT aria-hidden — the
          operable controls must stay in the accessibility tree. */}
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflow: "auto",
          display: "flex",
          justifyContent: "center",
          // The inner frame handles its own vertical alignment; starting at
          // the top lets tall mocks scroll naturally rather than being
          // clipped from both ends of a centered layout.
          alignItems: "flex-start",
          p: 3,
          ...CHECKER_BACKGROUND,
        }}
      >
        <Box
          sx={{
            width: frameWidth,
            maxWidth: "100%",
            // `transition` smooths the visual change when the admin cycles
            // device modes. Kept short so users aren't waiting on animation
            // to see the new layout.
            transition: "width 150ms ease",
          }}
        >
          {previewView === "access-gate" ? (
            <Card sx={{ maxWidth: 400, mx: "auto", mt: 4 }}>
              <CardContent>
                <Stack spacing={2} alignItems="center">
                  {portalData.logoUrl && (
                    <Box
                      component="img"
                      src={portalData.logoUrl}
                      alt=""
                      sx={{
                        width: deferredAppearance.branding.logoSize,
                        height: "auto",
                        objectFit: "contain",
                      }}
                    />
                  )}
                  <Typography variant="h6" align="center">
                    {portalData.name}
                  </Typography>
                  {accessMode === "token-protected" && (
                    <>
                      <TextField
                        label="Passphrase"
                        type="password"
                        size="small"
                        fullWidth
                        disabled
                        sx={{ pointerEvents: "none" }}
                      />
                      <Button
                        variant="contained"
                        fullWidth
                        sx={{ pointerEvents: "none" }}
                        startIcon={<LockIcon />}
                      >
                        Enter
                      </Button>
                    </>
                  )}
                  {accessMode === "cognito-groups" && (
                    <Button
                      variant="contained"
                      fullWidth
                      sx={{ pointerEvents: "none" }}
                      startIcon={<LockIcon />}
                    >
                      Sign in
                    </Button>
                  )}
                  {accessMode === "public" && (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <PublicIcon color="action" fontSize="small" />
                      <Typography variant="body2" color="text.secondary">
                        This portal is publicly accessible
                      </Typography>
                    </Stack>
                  )}
                </Stack>
              </CardContent>
            </Card>
          ) : (
            <PortalPreviewRenderer appearance={deferredAppearance} portalData={portalData} />
          )}
        </Box>
      </Box>
    </Box>
  );
};

export { PortalEditorPreview };
export default PortalEditorPreview;
