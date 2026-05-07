import React, { useCallback, useRef } from "react";
import {
  Box,
  Button,
  FormControlLabel,
  Slider,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";

import {
  useUploadPortalBanner,
  useUploadPortalFavicon,
  useUploadPortalLogo,
} from "@/api/hooks/usePortals";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";
import { readFileAsBase64 } from "../../../utils/readFileAsBase64";

/**
 * Maximum size (in bytes) accepted by either uploader. Mirrors the legacy
 * `ThumbnailSelector` limit (5 MB) which is the de facto cap the backend
 * enforces today. Kept as a module-level constant so both handlers share a
 * single source of truth.
 */
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

/**
 * Extract the uploaded key/URL from either legacy or new upload response
 * shapes. `useUploadPortalLogo` currently returns the unwrapped body
 * `{ success, data: { logoS3Key } }`; `useUploadPortalBanner` mirrors that // i18n-ignore
 * with `{ success, data: { bannerS3Key } }`. Callers of this helper pick // i18n-ignore
 * which nested field they want.
 */
const extractFromResponse = (response: unknown, keys: readonly string[]): string | undefined => {
  if (!response || typeof response !== "object") return undefined;
  // The hooks return `response.data` from axios, which axios sets to the
  // Lambda-unwrapped body. That body is `{ success, data }` where `data`
  // holds the fields we care about.
  const inner = (response as { data?: Record<string, unknown> }).data;
  if (!inner || typeof inner !== "object") {
    // Some response shapes skip the `data` wrapper; try the top level too.
    const top = response as Record<string, unknown>;
    for (const key of keys) {
      if (typeof top[key] === "string") return top[key] as string;
    }
    return undefined;
  }
  for (const key of keys) {
    if (typeof inner[key] === "string") return inner[key] as string;
  }
  return undefined;
};

/**
 * BrandingSection
 *
 * Edits `portalData.logoUrl`/`logoFile` and `appearance.branding`. Rendered
 * inside the sidebar's "Branding" accordion.
 *
 * Controls (top-to-bottom):
 *   1. Logo uploader (file input) — converts the selection to base64 via
 *      `FileReader.readAsDataURL` and, in edit mode, calls
 *      {@link useUploadPortalLogo} with `{ id, base64Image, contentType }`. // i18n-ignore
 *      The returned URL is stashed on `portalData.logoUrl`. In create mode
 *      (no `portalId`), the raw file is stashed on `portalData.logoFile`
 *      for deferred upload at save time (Requirements 7.1, 7.9).
 *   2. Logo-size slider (24-120, step 4) bound to
 *      `appearance.branding.logoSize` (Requirement 7.2).
 *   3. Show-powered-by switch bound to `appearance.branding.showPoweredBy`
 *      (Requirement 7.3).
 *   4. Banner uploader — POSTs to `/settings/portals/:id/banner` via
 *      {@link useUploadPortalBanner} and stores the returned S3 key on
 *      `appearance.branding.bannerS3Key`. Disabled in create mode with a
 *      tooltip explaining the user must save the portal first
 *      (Requirements 7.4, 7.6, 7.8).
 *   5. Banner-height slider (0-400, step 8) bound to
 *      `appearance.branding.bannerHeight`; 0 means no banner
 *      (Requirement 7.5).
 *   6. Remove logo button — clears both `logoUrl` and `logoFile` via
 *      `clearLogo()`; sets `isDirty = true` (Requirement 7.9). // i18n-ignore
 *   7. Remove banner button — clears `appearance.branding.bannerS3Key` via
 *      `updateBranding({ bannerS3Key: undefined })` (Requirement 7.9). // i18n-ignore
 *
 * Store subscriptions are fine-grained so editing one branding field does
 * not trigger re-renders of unrelated controls.
 */
const BrandingSection: React.FC = () => {
  const portalId = usePortalEditorStore((s) => s.portalData?.portalId);
  const logoUrl = usePortalEditorStore((s) => s.portalData?.logoUrl);
  const logoFile = usePortalEditorStore((s) => s.portalData?.logoFile);

  const logoSize = usePortalEditorStore((s) => s.appearance.branding.logoSize);
  const logoAlignment = usePortalEditorStore((s) => s.appearance.branding.logoAlignment);
  const showPoweredBy = usePortalEditorStore((s) => s.appearance.branding.showPoweredBy);
  const bannerS3Key = usePortalEditorStore((s) => s.appearance.branding.bannerS3Key);
  const bannerHeight = usePortalEditorStore((s) => s.appearance.branding.bannerHeight);
  const faviconS3Key = usePortalEditorStore((s) => s.appearance.branding.faviconS3Key);

  const updateBranding = usePortalEditorStore((s) => s.updateBranding);
  const updateLogoUrl = usePortalEditorStore((s) => s.updateLogoUrl);
  const setLogoFile = usePortalEditorStore((s) => s.setLogoFile);
  const clearLogo = usePortalEditorStore((s) => s.clearLogo);

  const uploadLogo = useUploadPortalLogo();
  const uploadBanner = useUploadPortalBanner();
  const uploadFavicon = useUploadPortalFavicon();

  const logoInputRef = useRef<HTMLInputElement | null>(null);
  const bannerInputRef = useRef<HTMLInputElement | null>(null);
  const faviconInputRef = useRef<HTMLInputElement | null>(null);

  const isCreateMode = !portalId;
  const hasLogo = Boolean(logoUrl) || Boolean(logoFile);

  // Generate a local object-URL preview when a File is stashed so the
  // admin sees the image they picked before saving. Revoked on unmount
  // or when the file changes to avoid memory leaks.
  const logoPreviewUrl = React.useMemo(() => {
    if (logoFile instanceof File) {
      return URL.createObjectURL(logoFile);
    }
    return null;
  }, [logoFile]);

  React.useEffect(() => {
    return () => {
      if (logoPreviewUrl) {
        URL.revokeObjectURL(logoPreviewUrl);
      }
    };
  }, [logoPreviewUrl]);

  // The displayable logo source: prefer the local preview (just-picked
  // file), fall back to the persisted URL (already-uploaded logo).
  const displayLogoSrc = logoPreviewUrl ?? (typeof logoUrl === "string" ? logoUrl : undefined);

  const handleLogoSelect = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      // Reset the input early so selecting the same file twice still fires
      // `onChange` — critical for re-uploading after a failed attempt.
      if (event.target) {
        event.target.value = "";
      }
      if (!file) return;

      if (!file.type.startsWith("image/") || file.size > MAX_UPLOAD_BYTES) {
        // Use a plain alert for parity with the legacy ThumbnailSelector;
        // proper toast wiring lands in Phase 5 (task 5.8).
        // eslint-disable-next-line no-alert
        alert("Please choose an image under 5 MB. For best results use a square PNG or SVG.");
        return;
      }

      if (isCreateMode) {
        // Create mode defers the upload until save — just remember the file.
        setLogoFile(file);
        return;
      }

      try {
        const { base64, contentType } = await readFileAsBase64(file);
        const response = await uploadLogo.mutateAsync({
          id: portalId as string,
          base64Image: base64,
          contentType,
        });
        // The backend may return `logoUrl` directly one day; today it only
        // returns `logoS3Key`. Store whichever is present — consumers treat
        // the value as an opaque reference.
        const resolved = extractFromResponse(response, ["logoUrl", "logoS3Key"]);
        if (resolved) {
          updateLogoUrl(resolved);
        }
      } catch {
        // `useUploadPortalLogo` already surfaces an error modal via its own
        // onError handler, so we just abort the flow here.
      }
    },
    [isCreateMode, portalId, setLogoFile, updateLogoUrl, uploadLogo]
  );

  const handleBannerSelect = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (event.target) {
        event.target.value = "";
      }
      if (!file) return;

      // Create mode is impossible here because the control is disabled, but
      // guarding is cheap and keeps the handler safe if future UI refactors
      // leave the input enabled by accident.
      if (isCreateMode || !portalId) {
        return;
      }

      if (!file.type.startsWith("image/") || file.size > MAX_UPLOAD_BYTES) {
        // eslint-disable-next-line no-alert
        alert("Please choose an image under 5 MB.");
        return;
      }

      try {
        const { base64, contentType } = await readFileAsBase64(file);
        const response = await uploadBanner.mutateAsync({
          id: portalId,
          base64Image: base64,
          contentType,
        });
        const key = extractFromResponse(response, ["bannerS3Key"]);
        const url = extractFromResponse(response, ["bannerUrl"]);
        if (key) {
          // Update both the S3 key and the resolved URL so the preview
          // refreshes immediately without waiting for a portal refetch.
          updateBranding({ bannerS3Key: key, ...(url ? { bannerUrl: url } : {}) });
        }
      } catch {
        // Error modal handled by the mutation's onError.
      }
    },
    [isCreateMode, portalId, updateBranding, uploadBanner]
  );

  const handleLogoSizeChange = useCallback(
    (_event: Event, value: number | number[]) => {
      if (typeof value !== "number") return;
      updateBranding({ logoSize: value });
    },
    [updateBranding]
  );

  const handleFaviconSelect = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (event.target) {
        event.target.value = "";
      }
      if (!file) return;

      if (isCreateMode || !portalId) {
        return;
      }

      // Accept ICO, PNG, and SVG favicons up to 1 MB
      const MAX_FAVICON_BYTES = 1 * 1024 * 1024;
      const allowedTypes = [
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/png",
        "image/svg+xml",
      ];
      if (!allowedTypes.includes(file.type) && !file.name.endsWith(".ico")) {
        // eslint-disable-next-line no-alert
        alert("Please choose an ICO, PNG, or SVG file under 1 MB.");
        return;
      }
      if (file.size > MAX_FAVICON_BYTES) {
        // eslint-disable-next-line no-alert
        alert("Please choose a file under 1 MB.");
        return;
      }

      try {
        const { base64, contentType } = await readFileAsBase64(file);
        const response = await uploadFavicon.mutateAsync({
          id: portalId,
          base64Image: base64,
          contentType,
        });
        const key = extractFromResponse(response, ["faviconS3Key"]);
        if (key) {
          updateBranding({ faviconS3Key: key });
        }
      } catch {
        // Error modal handled by the mutation's onError.
      }
    },
    [isCreateMode, portalId, updateBranding, uploadFavicon]
  );

  const handleRemoveFavicon = useCallback(() => {
    updateBranding({ faviconS3Key: undefined });
  }, [updateBranding]);

  const handleLogoAlignmentChange = useCallback(
    (_event: React.MouseEvent<HTMLElement>, value: "left" | "center" | null) => {
      if (value === null) return;
      updateBranding({ logoAlignment: value });
    },
    [updateBranding]
  );

  const handleBannerHeightChange = useCallback(
    (_event: Event, value: number | number[]) => {
      if (typeof value !== "number") return;
      updateBranding({ bannerHeight: value });
    },
    [updateBranding]
  );

  const handleShowPoweredByChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updateBranding({ showPoweredBy: checked });
    },
    [updateBranding]
  );

  const handleRemoveLogo = useCallback(() => {
    clearLogo();
  }, [clearLogo]);

  const handleRemoveBanner = useCallback(() => {
    updateBranding({ bannerS3Key: undefined });
  }, [updateBranding]);

  /**
   * Small wrapper around `Tooltip` that only mounts the tooltip when
   * `disabled` is true. Avoids a noisy "Save portal first..." hint in edit
   * mode while still enabling a clear explanation in create mode.
   */
  const BannerUploadControl = (
    <span>
      <Button
        component="label"
        variant="outlined"
        size="small"
        disabled={isCreateMode || uploadBanner.isPending}
      >
        {bannerS3Key ? "Replace banner" : "Upload banner"}
        <input
          ref={bannerInputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={handleBannerSelect}
        />
      </Button>
    </span>
  );

  return (
    <Stack spacing={2}>
      {/* Logo uploader */}
      <Stack spacing={1}>
        <Typography variant="caption" color="text.secondary">
          Logo
        </Typography>
        {displayLogoSrc && (
          <Box
            component="img"
            src={displayLogoSrc}
            alt="Logo preview"
            sx={{
              width: logoSize,
              height: logoSize,
              objectFit: "contain",
              borderRadius: 1,
              border: "1px solid",
              borderColor: "divider",
            }}
          />
        )}
        <Stack direction="row" spacing={1} alignItems="center">
          <Button component="label" variant="outlined" size="small" disabled={uploadLogo.isPending}>
            {hasLogo ? "Replace logo" : "Upload logo"}
            <input
              ref={logoInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={handleLogoSelect}
            />
          </Button>
          {hasLogo && (
            <Button
              onClick={handleRemoveLogo}
              variant="text"
              size="small"
              color="inherit"
              sx={{ textTransform: "none" }}
            >
              Remove logo
            </Button>
          )}
        </Stack>
        {isCreateMode && logoFile && (
          <Typography variant="caption" color="text.secondary">
            Logo will upload on Save
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary">
          Recommended: square PNG or SVG, at least 96×96 px, under 5 MB.
        </Typography>
      </Stack>

      {/* Logo alignment */}
      <Box>
        <Typography variant="caption" color="text.secondary" component="div">
          Logo alignment
        </Typography>
        <ToggleButtonGroup
          value={logoAlignment}
          exclusive
          onChange={handleLogoAlignmentChange}
          size="small"
          aria-label="Logo alignment"
          sx={{ mt: 0.5 }}
        >
          <ToggleButton value="left" aria-label="Align left">
            <FormatAlignLeftIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton value="center" aria-label="Align center">
            <FormatAlignCenterIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Logo size slider */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Logo size
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {logoSize}px
          </Typography>
        </Stack>
        <Slider
          value={logoSize}
          onChange={handleLogoSizeChange}
          min={24}
          max={120}
          step={4}
          size="small"
          aria-label="Logo size"
          valueLabelDisplay="auto"
        />
      </Box>

      {/* Show Powered By toggle */}
      <FormControlLabel
        control={
          <Switch checked={showPoweredBy} onChange={handleShowPoweredByChange} size="small" />
        }
        label='Show "Powered by Media Lake"'
      />

      {/* Banner uploader */}
      <Stack spacing={1}>
        <Typography variant="caption" color="text.secondary">
          Banner
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {isCreateMode ? (
            // i18n-ignore
            <Tooltip title="Save portal first to upload banner">{BannerUploadControl}</Tooltip>
          ) : (
            BannerUploadControl
          )}
          {bannerS3Key && !isCreateMode && (
            <Button
              onClick={handleRemoveBanner}
              variant="text"
              size="small"
              color="inherit"
              sx={{ textTransform: "none" }}
            >
              Remove banner
            </Button>
          )}
        </Stack>
      </Stack>

      {/* Banner height slider */}
      <Box>
        <Stack direction="row" alignItems="baseline" justifyContent="space-between">
          <Typography variant="caption" color="text.secondary">
            Banner height
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {bannerHeight === 0 ? "No banner" : `${bannerHeight}px`}
          </Typography>
        </Stack>
        <Slider
          value={bannerHeight}
          onChange={handleBannerHeightChange}
          min={0}
          max={400}
          step={8}
          size="small"
          aria-label="Banner height"
          valueLabelDisplay="auto"
        />
      </Box>

      {/* Favicon uploader */}
      <Stack spacing={1}>
        <Typography variant="caption" color="text.secondary">
          Favicon
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {isCreateMode ? (
            // i18n-ignore
            <Tooltip title="Save portal first to upload favicon">
              <span>
                <Button component="label" variant="outlined" size="small" disabled>
                  {faviconS3Key ? "Replace favicon" : "Upload favicon"}
                  <input
                    ref={faviconInputRef}
                    type="file"
                    accept=".ico,.png,.svg,image/x-icon,image/png,image/svg+xml"
                    hidden
                    onChange={handleFaviconSelect}
                  />
                </Button>
              </span>
            </Tooltip>
          ) : (
            <Button
              component="label"
              variant="outlined"
              size="small"
              disabled={uploadFavicon.isPending}
            >
              {faviconS3Key ? "Replace favicon" : "Upload favicon"}
              <input
                ref={faviconInputRef}
                type="file"
                accept=".ico,.png,.svg,image/x-icon,image/png,image/svg+xml"
                hidden
                onChange={handleFaviconSelect}
              />
            </Button>
          )}
          {faviconS3Key && !isCreateMode && (
            <Button
              onClick={handleRemoveFavicon}
              variant="text"
              size="small"
              color="inherit"
              sx={{ textTransform: "none" }}
            >
              Remove favicon
            </Button>
          )}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Recommended: 32×32 or 16×16 ICO/PNG, under 1 MB.
        </Typography>
      </Stack>
    </Stack>
  );
};

export { BrandingSection };
export default React.memo(BrandingSection);
