import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useSearchParams } from "react-router";
import { Alert, Box, Button, Paper, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import DOMPurify from "dompurify";

import type { PortalConfig } from "@/features/portal/types/portal.types";
import { createPortalApiClient } from "@/features/portal/api/portalApiClient";
import PortalAccessGate from "@/features/portal/components/PortalAccessGate";
import PortalHeader from "@/features/portal/components/PortalHeader";
import PortalDestinationSelector from "@/features/portal/components/PortalDestinationSelector";
import PortalPathBrowser from "@/features/portal/components/PortalPathBrowser";
import PortalPathBuilder from "@/features/portal/components/PortalPathBuilder";
import PortalMetadataForm from "@/features/portal/components/PortalMetadataForm";
import PortalUploader from "@/features/portal/components/PortalUploader";
import CaptchaGate from "@/features/portal/components/CaptchaGate";

import { DEFAULT_PORTAL_APPEARANCE } from "@/features/settings/upload-portals/constants/appearanceDefaults";
import type { PortalAppearance } from "@/features/settings/upload-portals/types/appearance.types";
import { createPortalTheme } from "@/features/settings/upload-portals/utils/createPortalTheme";
import { deepMerge } from "@/features/settings/upload-portals/utils/deepMerge";
import { loadGoogleFont } from "@/features/settings/upload-portals/utils/loadGoogleFont";

type AccessGateState = "gate" | "authenticated" | "unavailable";

/**
 * `appearance.layout.cardShadow` → MUI `Paper` elevation. Keep this mapping
 * in lockstep with `PortalPreviewRenderer` so the live-preview and the
 * real public page use identical elevations (Requirement 12.4).
 */
const CARD_SHADOW_ELEVATION: Record<PortalAppearance["layout"]["cardShadow"], number> = {
  none: 0,
  sm: 1,
  md: 3,
  lg: 8,
};

const UploadPortalPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams] = useSearchParams();

  const [sessionJwt, setSessionJwt] = useState<string | null>(null);
  const [portalConfig, setPortalConfig] = useState<PortalConfig | null>(null);
  const [selectedDestinationId, setSelectedDestinationId] = useState("");
  const [currentPath, setCurrentPath] = useState("");
  const [metadataValues, setMetadataValues] = useState<Record<string, string>>({});
  const [pathSegmentValues, setPathSegmentValues] = useState<Record<string, string>>({});
  const [isPathBrowserOpen, setIsPathBrowserOpen] = useState(false);
  const [accessGateState, setAccessGateState] = useState<AccessGateState>("gate");
  const [unavailableReason, setUnavailableReason] = useState<string>("");
  const [captchaVerified, setCaptchaVerified] = useState(false);

  const urlToken = searchParams.get("token");

  // ----- Appearance resolution (Requirement 12.1) -------------------------
  //
  // Deep-merge any `appearance` configured by the admin into the default
  // so portals without appearance data render identically to the
  // pre-visual-editor baseline (Requirement 12.2). `deepMerge` is typed
  // loosely so we route the call through `Record<string, unknown>` at the
  // boundary — runtime behavior matches the editor store's own usage.
  const appearance = useMemo<PortalAppearance>(() => {
    if (!portalConfig?.appearance) return DEFAULT_PORTAL_APPEARANCE;
    return deepMerge(
      structuredClone(DEFAULT_PORTAL_APPEARANCE) as unknown as Record<string, unknown>,
      portalConfig.appearance as unknown as Record<string, unknown>
    ) as unknown as PortalAppearance;
  }, [portalConfig?.appearance]);

  // Scoped MUI theme matching the editor's preview wrapper — same
  // `createPortalTheme` factory so the live-preview renders exactly what
  // the public page will render (Requirement 12.3).
  const portalTheme = useMemo(() => createPortalTheme(appearance), [appearance]);

  // Load the configured Google Fonts on mount and whenever the families
  // change (Requirement 12.3). `loadGoogleFont` is idempotent so mounting
  // twice with the same family is a no-op.
  useEffect(() => {
    loadGoogleFont(appearance.typography.headingFontFamily);
    loadGoogleFont(appearance.typography.bodyFontFamily);
  }, [appearance.typography.headingFontFamily, appearance.typography.bodyFontFamily]);

  // Inject a custom favicon when the admin has configured one.
  useEffect(() => {
    const faviconUrl = appearance.branding.faviconUrl;
    if (!faviconUrl) return;

    // Remove any existing portal-injected favicon link
    const existingLink = document.querySelector<HTMLLinkElement>(
      'link[data-portal-favicon="true"]'
    );
    if (existingLink) {
      existingLink.href = faviconUrl;
      return;
    }

    const link = document.createElement("link");
    link.rel = "icon";
    link.href = faviconUrl;
    link.setAttribute("data-portal-favicon", "true");
    document.head.appendChild(link);

    return () => {
      link.remove();
    };
  }, [appearance.branding.faviconUrl]);

  const resolveInitialPath = useCallback(
    async (
      client: ReturnType<typeof createPortalApiClient>,
      destinationId: string,
      rootPath: string | undefined,
      prefixParam: string
    ): Promise<string> => {
      if (prefixParam) return prefixParam;
      if (rootPath) return rootPath;
      try {
        const { data } = await client.get(`/portal/${slug}/browse`, {
          params: { destinationId },
        });
        return data.prefix ?? "";
      } catch {
        return "";
      }
    },
    [slug]
  );

  // Pre-populate values from URL params
  const prePopulatedValues = useMemo(() => {
    const vals: Record<string, string> = {};
    searchParams.forEach((value, key) => {
      if (key !== "token") vals[key] = value;
    });
    return vals;
  }, [searchParams]);

  // Session expiry timer (1 hour)
  useEffect(() => {
    if (!sessionJwt) return;
    const timer = setTimeout(() => {
      setSessionJwt(null);
      setAccessGateState("gate");
    }, 3600 * 1000);
    return () => clearTimeout(timer);
  }, [sessionJwt]);

  const handleSessionEstablished = useCallback(
    async (jwt: string) => {
      setSessionJwt(jwt);
      try {
        const client = createPortalApiClient(jwt);
        const { data } = await client.get(`/portal/${slug}`);
        const config = data as PortalConfig;
        setPortalConfig(config);
        const firstDest = [...config.destinations].sort((a, b) => a.order - b.order)[0];
        if (firstDest) {
          setSelectedDestinationId(firstDest.destinationId);
          const resolved = await resolveInitialPath(
            client,
            firstDest.destinationId,
            firstDest.rootPath,
            searchParams.get("prefix") ?? ""
          );
          setCurrentPath(resolved);
        }
        setMetadataValues(prePopulatedValues);
        setPathSegmentValues(prePopulatedValues);
        setAccessGateState("authenticated");
      } catch (err) {
        console.error("Failed to load portal config:", err);
        setSessionJwt(null);
        setAccessGateState("gate");
      }
    },
    [slug, prePopulatedValues, searchParams, resolveInitialPath]
  );

  const handleSessionExpired = useCallback(() => {
    setSessionJwt(null);
    setAccessGateState("gate");
  }, []);

  const handlePortalUnavailable = useCallback((reason: "inactive" | "expired") => {
    setUnavailableReason(
      reason === "inactive"
        ? "This upload portal is currently inactive."
        : "This upload portal has expired."
    );
    setAccessGateState("unavailable");
  }, []);

  const selectedDestination = portalConfig?.destinations.find(
    (d) => d.destinationId === selectedDestinationId
  );

  const handleDestinationChange = useCallback(
    async (destId: string) => {
      setSelectedDestinationId(destId);
      const dest = portalConfig?.destinations.find((d) => d.destinationId === destId);
      if (dest && sessionJwt) {
        const client = createPortalApiClient(sessionJwt);
        const resolved = await resolveInitialPath(
          client,
          dest.destinationId,
          dest.rootPath,
          searchParams.get("prefix") ?? ""
        );
        setCurrentPath(resolved);
      }
    },
    [portalConfig, sessionJwt, resolveInitialPath, searchParams]
  );

  // Sanitized footer HTML — memoized so rapid re-renders don't re-run
  // DOMPurify. Kept outside the JSX so it's easy to reuse across render
  // branches and to short-circuit the "render nothing" case.
  const sanitizedFooterHtml = useMemo(() => {
    const raw = appearance.content.footerHtml;
    if (!raw || !raw.trim()) return "";
    return DOMPurify.sanitize(raw);
  }, [appearance.content.footerHtml]);
  const hasFooterHtml = sanitizedFooterHtml.length > 0;

  if (!slug) return null;

  return (
    <Box
      sx={{
        // Apply the admin-configured page background (Requirement 12.4).
        background: appearance.colors.background,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        // Vertical padding is stored in px; express via `py` as a direct
        // pixel value so the layout tracks the editor setting exactly
        // (Requirement 12.4).
        py: `${appearance.layout.pageVerticalPadding}px`,
        px: 2,
      }}
    >
      <ThemeProvider theme={portalTheme}>
        <Paper
          elevation={CARD_SHADOW_ELEVATION[appearance.layout.cardShadow]}
          sx={{
            width: "100%",
            maxWidth: appearance.layout.cardMaxWidth,
            borderRadius: `${appearance.layout.cardBorderRadius}px`,
            overflow: "hidden",
            backgroundColor: appearance.colors.cardBackground,
            border: appearance.layout.cardBorder ? `1px solid ${appearance.colors.border}` : "none",
          }}
        >
          {accessGateState === "unavailable" && (
            <Box sx={{ p: 4 }}>
              <Alert severity="warning">{unavailableReason}</Alert>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 2, textAlign: "center" }}
              >
                Contact the portal administrator for a new link.
              </Typography>
            </Box>
          )}

          {accessGateState === "gate" && (
            <PortalAccessGate
              slug={slug}
              urlToken={urlToken}
              onSessionEstablished={handleSessionEstablished}
              onPortalUnavailable={handlePortalUnavailable}
            />
          )}

          {accessGateState === "authenticated" &&
            sessionJwt &&
            portalConfig &&
            selectedDestination && (
            <>
              {/*
               * Banner (Requirement 12.6 / 7.7). Rendered inside the card
               * so the `overflow: hidden` on `Paper` crops it to the // i18n-ignore
               * configured `cardBorderRadius`. Only visible when the
               * admin has both configured a banner height > 0 AND the
               * backend resolved a usable URL.
               */}
              {appearance.branding.bannerHeight > 0 && appearance.branding.bannerUrl && (
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
              <PortalHeader
                name={portalConfig.name}
                description={portalConfig.description}
                logoUrl={portalConfig.logoUrl}
                titleHtml={appearance.content.titleHtml}
                descriptionHtml={appearance.content.descriptionHtml}
                logoSize={appearance.branding.logoSize}
                logoAlignment={appearance.branding.logoAlignment}
              />
              <CaptchaGate
                captchaEnabled={portalConfig.captchaEnabled}
                onCaptchaComplete={() => setCaptchaVerified(true)}
              >
                <Box
                  sx={{
                    // Apply admin-configured card padding
                    // (Requirement 12.4). The legacy layout used
                    // "24px 32px" which is roughly equivalent to
                    // `cardPadding = 32` at today's defaults; switching
                    // to the configured value makes the card padding
                    // adjustable end-to-end.
                    p: `${appearance.layout.cardPadding}px`,
                    display: "flex",
                    flexDirection: "column",
                    gap: 2.5,
                  }}
                >
                  {portalConfig.destinations.length > 1 && (
                    <PortalDestinationSelector
                      destinations={portalConfig.destinations}
                      selectedDestinationId={selectedDestinationId}
                      onChange={handleDestinationChange}
                    />
                  )}

                  {selectedDestination.allowBrowsing && (
                    <>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setIsPathBrowserOpen(true)}
                        sx={{ alignSelf: "flex-start" }}
                      >
                        Browse: {currentPath || "/"}
                      </Button>
                      <PortalPathBrowser
                        open={isPathBrowserOpen}
                        onClose={() => setIsPathBrowserOpen(false)}
                        slug={slug}
                        sessionJwt={sessionJwt}
                        destination={selectedDestination}
                        currentPath={currentPath}
                        onPathSelect={(path) => {
                          setCurrentPath(path);
                          setIsPathBrowserOpen(false);
                        }}
                      />
                    </>
                  )}

                  {portalConfig.structuredPathMode &&
                    selectedDestination.pathSegments &&
                    selectedDestination.pathSegments.length > 0 && (
                      <PortalPathBuilder
                        pathSegments={selectedDestination.pathSegments}
                        prePopulatedValues={pathSegmentValues}
                        onChange={(path, isValid) => {
                          if (isValid) {
                            setCurrentPath((selectedDestination.rootPath ?? "") + path + "/");
                          }
                        }}
                      />
                    )}

                  {portalConfig.metadataFields.length > 0 && (
                    <PortalMetadataForm
                      fields={portalConfig.metadataFields}
                      prePopulatedValues={prePopulatedValues}
                      onChange={(values) => setMetadataValues(values)}
                    />
                  )}

                  <PortalUploader
                    portalSlug={slug}
                    sessionJwt={sessionJwt}
                    destination={selectedDestination}
                    currentPath={currentPath}
                    metadataFields={metadataValues}
                    maxFileSizeBytes={portalConfig.maxFileSizeBytes}
                    maxFilesPerSession={portalConfig.maxFilesPerSession}
                    onSessionExpired={handleSessionExpired}
                    useCaptchaIntegration={portalConfig.captchaEnabled}
                    submitButtonText={appearance.content.submitButtonText}
                    successMessage={appearance.content.successMessage}
                    dropZoneText={appearance.content.dropZoneText}
                    allowedFileTypes={portalConfig.allowedFileTypes ?? []}
                    buttonStyle={appearance.content.buttonStyle}
                    buttonRounding={appearance.content.buttonRounding}
                  />
                </Box>
                {/*
                 * Footer (Requirements 12.12 / 12.13 / 12.14):
                 *   - Admin-authored `footerHtml` renders (DOMPurify-
                 *     sanitized) when non-empty.
                 *   - "Powered by MediaLake" renders when
                 *     `showPoweredBy === true`. When both are absent, // i18n-ignore
                 *     skip the footer container entirely so the card
                 *     ends cleanly on the upload button.
                 */}
                {(hasFooterHtml || appearance.branding.showPoweredBy) && (
                  <Box
                    sx={{
                      p: "12px 32px",
                      borderTop: "1px solid",
                      borderColor: "divider",
                      textAlign: "center",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: hasFooterHtml && appearance.branding.showPoweredBy ? 1 : 0,
                    }}
                  >
                    {hasFooterHtml && (
                      <Box
                        sx={{
                          "& p": { m: 0 },
                          color: "text.secondary",
                          wordBreak: "break-word",
                        }}
                        dangerouslySetInnerHTML={{ __html: sanitizedFooterHtml }}
                      />
                    )}
                    {appearance.branding.showPoweredBy && (
                      <Typography variant="caption" color="text.secondary">
                        Powered by Media Lake
                      </Typography>
                    )}
                  </Box>
                )}
              </CaptchaGate>
            </>
          )}
        </Paper>
      </ThemeProvider>
    </Box>
  );
};

export default UploadPortalPage;
