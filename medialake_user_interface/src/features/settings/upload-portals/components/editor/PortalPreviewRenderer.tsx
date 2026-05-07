import React, { useMemo } from "react";
import {
  Alert,
  Box,
  Button,
  Paper,
  ScopedCssBaseline,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DOMPurify from "dompurify";

import type { PortalDestination, PortalMetadataField } from "@/api/types/api.types";

import type { PortalAppearance } from "../../types/appearance.types";
import { createPortalTheme } from "../../utils/createPortalTheme";

/**
 * Props for {@link PortalPreviewRenderer}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces". The `destinations`
 * slot is accepted for API parity with the public portal but is not rendered
 * in the preview mock — the preview exists to show the admin how the page
 * looks, not to expose a destination picker.
 */
export interface PortalPreviewRendererProps {
  appearance: PortalAppearance;
  portalData: {
    name: string;
    logoUrl?: string;
    metadataFields: PortalMetadataField[];
    destinations: PortalDestination[];
  };
}

/**
 * Map the four `PortalAppearanceLayout.cardShadow` enum values onto MUI
 * `Paper` elevation levels. Values match the mapping documented in the task
 * spec: `"none"` → 0, `"sm"` → 1, `"md"` → 3, `"lg"` → 8.
 */
const CARD_SHADOW_ELEVATION: Record<PortalAppearance["layout"]["cardShadow"], number> = {
  none: 0,
  sm: 1,
  md: 3,
  lg: 8,
};

/**
 * Type the `disabled` form control field `type` accepts.
 *
 * MUI's `TextField` `type` prop accepts a small set of HTML input types. The
 * metadata-field `"select"` case is rendered as a plain `text` input here —
 * the preview is intentionally non-interactive, so we don't need to spin up
 * a real `Select` component with dummy options.
 */
const metadataTypeToInputType = (
  fieldType: PortalMetadataField["type"]
): React.InputHTMLAttributes<HTMLInputElement>["type"] => {
  switch (fieldType) {
    case "email":
      return "email";
    case "number":
      return "number";
    default:
      return "text";
  }
};

/**
 * PortalPreviewRenderer
 *
 * Renders a scoped, non-interactive mock of the public upload-portal page
 * using a `PortalAppearance` snapshot. The renderer powers the live preview
 * panel in the visual editor (Requirements 3.2, 3.7, 3.9, 17.3) and must
 * not leak its theme or CSS resets out to the surrounding editor chrome.
 *
 * Isolation layers (outside-in):
 *   1. `<Box sx={{ all: "initial", display: "contents" }}>` — CSS reset
 *      boundary. Stops inherited typography, color, and spacing from the
 *      editor chrome from bleeding into the mock portal page
 *      (Requirement 3.7).
 *   2. `<ThemeProvider theme={createPortalTheme(appearance)}>` — scoped
 *      MUI theme built from the appearance snapshot so that every MUI
 *      component below it renders with the admin's chosen palette,
 *      typography, shape, and component overrides (Requirement 3.2).
 *   3. `<ScopedCssBaseline>` — applies MUI's baseline styles (background,
 *      default text color, `box-sizing: border-box`) only within the // i18n-ignore
 *      preview subtree instead of globally.
 *   4. The mock card itself (banner, header, metadata form, upload drop
 *      zone, submit button, footer).
 *
 * HTML content (`titleHtml`, `descriptionHtml`, `footerHtml`) is always
 * passed through DOMPurify before being injected via
 * `dangerouslySetInnerHTML`. The defense-in-depth rationale:
 *   - Tiptap's output is already structured HTML, but the admin-facing
 *     editor still routes user-generated HTML through this renderer.
 *   - The public portal page uses the same pattern (task 6.9), so keeping
 *     sanitization co-located with the preview guarantees parity.
 *
 * Wrapping the component in `React.memo` (at the bottom of the file) means
 * the expensive theme construction + DOM sanitization run only when one of
 * the two props actually changes. Callers use `useDeferredValue` on
 * `appearance` (see task 4.6) to further coalesce rapid edits.
 */
const PortalPreviewRendererComponent: React.FC<PortalPreviewRendererProps> = ({
  appearance,
  portalData,
}) => {
  const theme = useMemo(() => createPortalTheme(appearance), [appearance]);

  // Sanitize every HTML string once per `appearance` change. DOMPurify is
  // synchronous and fast, but we memoize anyway to keep the render function
  // cheap when only, say, a color changes (the HTML strings stay identical).
  const sanitizedTitle = useMemo(
    () => DOMPurify.sanitize(appearance.content.titleHtml ?? ""),
    [appearance.content.titleHtml]
  );
  const sanitizedDescription = useMemo(
    () => DOMPurify.sanitize(appearance.content.descriptionHtml ?? ""),
    [appearance.content.descriptionHtml]
  );
  const sanitizedFooter = useMemo(
    () => DOMPurify.sanitize(appearance.content.footerHtml ?? ""),
    [appearance.content.footerHtml]
  );

  const hasTitleHtml = sanitizedTitle.trim().length > 0;
  const hasDescriptionHtml = sanitizedDescription.trim().length > 0;
  const hasFooterHtml = sanitizedFooter.trim().length > 0;

  const shouldRenderBanner =
    appearance.branding.bannerHeight > 0 && !!appearance.branding.bannerUrl;

  const cardElevation = CARD_SHADOW_ELEVATION[appearance.layout.cardShadow];

  return (
    // Layer 1: CSS reset boundary. `display: contents` removes the box from
    // layout so the preview frame sizing rules still apply to the card.
    <Box sx={{ all: "initial", display: "contents" }}>
      {/* Layer 2: scoped MUI theme. */}
      <ThemeProvider theme={theme}>
        {/* Layer 3: scoped baseline styles. */}
        <ScopedCssBaseline>
          {/* Layer 4: the mock card. */}
          <Paper
            elevation={cardElevation}
            sx={{
              maxWidth: appearance.layout.cardMaxWidth,
              width: "100%",
              mx: "auto",
              overflow: "hidden",
              // `Paper` doesn't apply its own padding — push that through sx
              // so the banner can bleed edge-to-edge while the rest of the
              // card uses the configured padding.
              backgroundColor: appearance.colors.cardBackground,
            }}
          >
            {/* Optional banner — bleeds to the card edges above the padded
                content below. */}
            {shouldRenderBanner && (
              <Box
                component="img"
                src={appearance.branding.bannerUrl}
                alt=""
                sx={{
                  display: "block",
                  width: "100%",
                  height: appearance.branding.bannerHeight,
                  objectFit: "cover",
                }}
              />
            )}

            <Box sx={{ p: `${appearance.layout.cardPadding}px` }}>
              {/* Header: logo + sanitized title + sanitized description. */}
              <Stack
                spacing={2}
                sx={{
                  mb: 3,
                  alignItems:
                    appearance.branding.logoAlignment === "center" ? "center" : "flex-start",
                  textAlign: appearance.branding.logoAlignment === "center" ? "center" : "left",
                }}
              >
                {portalData.logoUrl ? (
                  <Box
                    component="img"
                    src={portalData.logoUrl}
                    alt=""
                    sx={{
                      width: appearance.branding.logoSize,
                      height: "auto",
                      objectFit: "contain",
                    }}
                  />
                ) : (
                  <CloudUploadIcon
                    sx={{
                      fontSize: appearance.branding.logoSize,
                      color: "primary.main",
                    }}
                  />
                )}

                {hasTitleHtml ? (
                  <Box
                    sx={{ "& p": { m: 0 } }}
                    dangerouslySetInnerHTML={{ __html: sanitizedTitle }}
                  />
                ) : (
                  <Typography variant="h5" component="h1">
                    {portalData.name}
                  </Typography>
                )}

                {hasDescriptionHtml && (
                  <Box
                    sx={{ "& p": { m: 0 }, color: "text.secondary" }}
                    dangerouslySetInnerHTML={{ __html: sanitizedDescription }}
                  />
                )}
              </Stack>

              {/* Mock metadata form. `pointer-events: none` keeps the fields // i18n-ignore
                  visually present but non-interactive, matching the
                  preview's role as a display surface. */}
              <Stack spacing={2} sx={{ mb: 3, pointerEvents: "none" }} aria-hidden="true">
                {portalData.metadataFields.map((field, index) => (
                  <TextField
                    key={`${field.label}-${index}`}
                    label={field.label}
                    type={metadataTypeToInputType(field.type)}
                    required={field.required}
                    fullWidth
                    size="small"
                    variant="outlined"
                    tabIndex={-1}
                    slotProps={{
                      input: {
                        readOnly: true,
                        tabIndex: -1,
                      },
                    }}
                  />
                ))}
              </Stack>

              {/* Mock upload drop zone. Decorative only, hence the dashed
                  border + static copy. */}
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 1,
                  py: 4,
                  px: 2,
                  mb: 3,
                  borderRadius: 1,
                  border: "1px dashed",
                  borderColor: "divider",
                  color: "text.secondary",
                }}
              >
                <CloudUploadIcon fontSize="large" />
                <Typography variant="body2">
                  {appearance.content.dropZoneText || "Drop files here or click to browse"}
                </Typography>
              </Box>

              {/* Success message preview — always visible so the admin can
                  see how it looks. */}
              {appearance.content.successMessage && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  {appearance.content.successMessage}
                </Alert>
              )}

              {/* Mock submit button — visually active but non-interactive
                  via pointer-events:none (the whole preview is aria-hidden
                  and non-interactive). Using `disabled` would wash out the
                  button color making it invisible. */}
              <Button
                variant={appearance.content.buttonStyle || "contained"}
                fullWidth
                sx={{
                  pointerEvents: "none",
                  mb: hasFooterHtml || appearance.branding.showPoweredBy ? 3 : 0,
                  borderRadius:
                    appearance.content.buttonRounding === "square"
                      ? 0
                      : appearance.content.buttonRounding === "pill"
                        ? "9999px"
                        : undefined,
                }}
                tabIndex={-1}
              >
                {appearance.content.submitButtonText}
              </Button>

              {/* Footer: optional sanitized HTML + optional Powered By. */}
              {(hasFooterHtml || appearance.branding.showPoweredBy) && (
                <Stack spacing={1} sx={{ alignItems: "center" }}>
                  {hasFooterHtml && (
                    <Box
                      sx={{
                        "& p": { m: 0 },
                        color: "text.secondary",
                        textAlign: "center",
                      }}
                      dangerouslySetInnerHTML={{ __html: sanitizedFooter }}
                    />
                  )}
                  {appearance.branding.showPoweredBy && (
                    <Typography variant="caption" color="text.secondary">
                      Powered by Media Lake
                    </Typography>
                  )}
                </Stack>
              )}
            </Box>
          </Paper>
        </ScopedCssBaseline>
      </ThemeProvider>
    </Box>
  );
};

/**
 * Memoized export. The preview panel wraps this component in a
 * `useDeferredValue` + `useMemo` boundary, but we still benefit from
 * `React.memo` so that unrelated editor re-renders (e.g. sidebar accordion
 * state) never reach the expensive theme/DOM-sanitization work inside.
 */
export const PortalPreviewRenderer = React.memo(PortalPreviewRendererComponent);

export default PortalPreviewRenderer;
