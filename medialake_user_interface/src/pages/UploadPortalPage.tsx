import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import { Alert, Box, Paper, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import DOMPurify from "dompurify";

import { Model } from "survey-core";
import { Survey } from "survey-react-ui";
// SurveyJS default theme stylesheet. Global import (same one the live preview
// uses in `PortalPreviewRenderer`) so the public survey DOM renders styled.
// The scoped `createPortalTheme` + the card chrome still own the surrounding
// branding; this only styles the SurveyJS body itself.
import "survey-core/survey-core.min.css";

import type { PortalConfig } from "@/features/portal/types/portal.types";
import { createPortalApiClient } from "@/features/portal/api/portalApiClient";
import PortalAccessGate from "@/features/portal/components/PortalAccessGate";
import PortalHeader from "@/features/portal/components/PortalHeader";
import CaptchaGate from "@/features/portal/components/CaptchaGate";

import { DEFAULT_PORTAL_APPEARANCE } from "@/features/settings/upload-portals/constants/appearanceDefaults";
import type { PortalAppearance } from "@/features/settings/upload-portals/types/appearance.types";
import { createPortalTheme } from "@/features/settings/upload-portals/utils/createPortalTheme";
import { deepMerge } from "@/features/settings/upload-portals/utils/deepMerge";
import { loadGoogleFont } from "@/features/settings/upload-portals/utils/loadGoogleFont";

// Req 11.3 / 6.2: the public renderer builds its schema EXCLUSIVELY through the
// shared `buildSurveyJson` + `registerPortalQuestions` — the SAME modules the
// admin live preview uses (Task 14) — so there is no second schema path.
import { buildSurveyJson } from "@/features/settings/upload-portals/shared/portalSurveyModel";
import { registerPortalQuestions } from "@/features/settings/upload-portals/shared/registerPortalQuestions";
// Side-effect import: binds the four custom question React renderers (incl. the
// LIVE Uppy uploader, which renders for real in `mode: "public"`). The module
// self-registers at import and the registration is idempotent.
import "@/features/settings/upload-portals/shared/questions/registerPortalQuestionRenderers";
import {
  PortalRuntimeContext,
  type PortalRuntimeValue,
  CURRENT_PATH_KEY,
  UPLOAD_IN_PROGRESS_KEY,
  UPLOAD_SESSION_ID_KEY,
  UPLOADED_FILE_COUNT_KEY,
  collectMetadataValues,
} from "@/features/settings/upload-portals/shared/PortalRuntimeContext";
import { usePortalApi } from "@/features/portal/hooks/usePortalApi";

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
  const { t } = useTranslation();

  const [sessionJwt, setSessionJwt] = useState<string | null>(null);
  const [portalConfig, setPortalConfig] = useState<PortalConfig | null>(null);
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
        setAccessGateState("authenticated");
      } catch (err) {
        console.error("Failed to load portal config:", err);
        setSessionJwt(null);
        setAccessGateState("gate");
      }
    },
    [slug]
  );

  // Session-expiry handler (Requirement 15.2). Resetting to the gate clears the
  // live session and unmounts the survey host below, discarding the in-progress
  // `survey.data` (a fresh survey is built on re-authentication). The live
  // uploader question invokes this through `runtime.onSessionExpired` on a 401,
  // so a mid-flow expiry resets to the gate exactly like the legacy behavior.
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

  // ----- SurveyJS multi-page flow (Requirements 11.3 / 11.4 / 5.5) --------
  //
  // Build the SurveyJS model from the persisted pages via the shared
  // `buildSurveyJson`, in EDIT (interactive) mode with the LIVE Uppy uploader.
  // Keyed on `sessionJwt` + `portalConfig` so a session expiry → re-auth cycle
  // produces a fresh model with empty `survey.data` (Requirement 15.2). URL
  // params are seeded into `survey.data` so pre-populated metadata answers and
  // any pre-selected reserved keys carry into the flow.
  const survey = useMemo(() => {
    if (!sessionJwt || !portalConfig) return null;
    // Idempotent — guarantees the custom question MODELS exist even if the
    // renderer side-effect import was tree-shaken in some build path.
    registerPortalQuestions();
    const model = new Model(buildSurveyJson(portalConfig));
    model.mode = "edit";
    // The card chrome (PortalHeader) renders the portal title; suppress the
    // survey's own title so it is not duplicated.
    model.showTitle = false;
    // Render the per-page title ourselves (as a heading above the body, under
    // the logo) so the public page matches the admin live preview exactly.
    // Without this, SurveyJS renders its native page title in a different
    // position (Requirement: preview ↔ public parity).
    model.showPageTitles = false;
    // Submit (the SurveyJS Complete button on the last page) is the
    // AUTHORITATIVE pipeline trigger — it captures the final form snapshot and
    // marks the session submitted (see post_submit). Show it only when the
    // portal collects a form submission; an upload-only portal
    // (formSubmissionEnabled === false) has no Submit button, so
    // formSubmissionComplete stays false. The onComplete / onCompleting handlers
    // are wired in a separate effect below.
    const submissionEnabled = portalConfig.formSubmissionEnabled ?? true;
    model.showCompleteButton = submissionEnabled;
    model.showCompletedPage = submissionEnabled;
    // Localized label for the authoritative Submit button (distinct from the
    // uploader's own "Upload assets" button inside the uploader question).
    model.completeText = t("uploadPortals.public.submit");
    if (Object.keys(prePopulatedValues).length > 0) {
      // Seed pre-populated answers without discarding any SurveyJS defaults.
      model.data = { ...model.data, ...prePopulatedValues };
    }
    return model;
  }, [sessionJwt, portalConfig, prePopulatedValues, t]);

  // Track the survey's current page so the heading we render (below) matches
  // the page actually shown — multi-page surveys display one page at a time.
  const [currentPageNo, setCurrentPageNo] = useState(0);
  useEffect(() => {
    if (!survey) return;
    setCurrentPageNo(survey.currentPageNo);
    const handler = (sender: Model) => setCurrentPageNo(sender.currentPageNo);
    survey.onCurrentPageChanged.add(handler);
    return () => survey.onCurrentPageChanged.remove(handler);
  }, [survey]);

  // Portal API for the submit call fired on survey completion. Uses the live
  // session JWT and honors the portal's CAPTCHA/WAF integration.
  const portalApi = usePortalApi(slug ?? "", sessionJwt, portalConfig?.captchaEnabled);

  // Submit (Complete) is the authoritative pipeline trigger. On completion we
  // POST the final form snapshot + the count of successfully uploaded files to
  // /submit (see post_submit), which marks the session submitted and lets the
  // two-signal join fire. onCompleting blocks Submit while an upload is still
  // in flight so the count/marker reflect a settled batch. The uploader writes
  // the session id, uploaded count, and in-progress flag into reserved
  // survey-data keys (see UppyUploaderQuestion / PortalRuntimeContext).
  useEffect(() => {
    if (!survey) return;

    const onCompleting = (_sender: Model, options: { allow: boolean }) => {
      if (survey.getValue(UPLOAD_IN_PROGRESS_KEY) === true) {
        options.allow = false;
      }
    };

    const onComplete = (sender: Model) => {
      const sessionId = sender.getValue(UPLOAD_SESSION_ID_KEY) as string | undefined;
      if (!sessionId) return;
      const metadata = collectMetadataValues(sender);
      const rawCount = sender.getValue(UPLOADED_FILE_COUNT_KEY);
      const fileCount = typeof rawCount === "number" ? rawCount : undefined;
      portalApi.submit(sessionId, { metadata, fileCount }).catch(() => {
        // best-effort from the client; the server sweep reconciles a missed
        // submit, and submit is idempotent on the marker.
      });
    };

    survey.onCompleting.add(onCompleting);
    survey.onComplete.add(onComplete);
    return () => {
      survey.onCompleting.remove(onCompleting);
      survey.onComplete.remove(onComplete);
    };
  }, [survey, portalApi]);

  // Session heartbeat — lifted from the uploader to the page so it runs for the
  // ENTIRE life of the authenticated survey (any page, upload in flight or not).
  // This makes the server-side "idle" timeout mean "the browser is gone" rather
  // than "uploads finished", so a user still filling out the form after
  // uploading is never swept. Best-effort and server-rate-limited; it reads the
  // live session id the uploader writes into survey.data, so it starts pinging
  // as soon as a session exists and stops when the survey unmounts.
  useEffect(() => {
    if (!survey) return;
    const HEARTBEAT_INTERVAL_MS = 30_000;
    const interval = setInterval(() => {
      const sessionId = survey.getValue(UPLOAD_SESSION_ID_KEY) as string | undefined;
      if (sessionId) {
        portalApi.heartbeat(sessionId).catch(() => {
          // best-effort; a failed heartbeat must not disrupt the flow
        });
      }
    }, HEARTBEAT_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [survey, portalApi]);

  // The current page's title, rendered as a heading above the survey body so
  // the public page mirrors the admin live preview (title under the logo).
  // `buildSurveyJson` sorts pages by ascending pageNumber, so the survey's page
  // index aligns with the sorted order here.
  const currentPageTitle = useMemo(() => {
    const pages = portalConfig?.pages ?? [];
    const sorted = [...pages].sort((a, b) => a.pageNumber - b.pageNumber);
    return sorted[currentPageNo]?.title ?? "";
  }, [portalConfig, currentPageNo]);

  // Resolve the initial upload path when a destination is selected
  // (auto-selected on a single-destination page, or chosen by the user). The
  // destination-selector question writes `__selectedDestinationId` and then
  // calls this; we resolve the prefix exactly as the legacy page did and thread
  // it through `survey.data` under `__currentPath`. The path-browser /
  // path-builder questions overwrite `__currentPath` when the user refines it.
  const handleDestinationChange = useCallback(
    async (destinationId: string) => {
      if (!survey || !portalConfig || !sessionJwt) return;
      const dest = portalConfig.destinations?.find((d) => d.destinationId === destinationId);
      if (!dest) return;
      const client = createPortalApiClient(sessionJwt);
      const resolved = await resolveInitialPath(
        client,
        dest.destinationId,
        dest.rootPath,
        searchParams.get("prefix") ?? ""
      );
      survey.setValue(CURRENT_PATH_KEY, resolved);
    },
    [survey, portalConfig, sessionJwt, resolveInitialPath, searchParams]
  );

  // The path questions already write `__currentPath` into `survey.data`
  // themselves; the survey owns that state, so the page does not need to mirror
  // it. Provided for the runtime contract / future extensibility.
  const handlePathChange = useCallback(() => {}, []);

  // Runtime surface shared with every custom SurveyJS question (Req 11.3). Live
  // mode wires the real API session + Uppy and threads `onSessionExpired` so a
  // mid-flow 401 resets to the gate (Requirement 15.2).
  const runtimeValue = useMemo<PortalRuntimeValue>(
    () => ({
      mode: "public",
      slug: slug ?? "",
      sessionJwt,
      config: portalConfig,
      onSessionExpired: handleSessionExpired,
      onDestinationChange: handleDestinationChange,
      onPathChange: handlePathChange,
    }),
    [
      slug,
      sessionJwt,
      portalConfig,
      handleSessionExpired,
      handleDestinationChange,
      handlePathChange,
    ]
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
            maxWidth: `${appearance.layout.cardMaxWidth}px`,
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

          {/*
           * Until a session exists, render ONLY the access gate — no page
           * content, no multi-page flow (Requirement 11.2).
           */}
          {accessGateState === "gate" && (
            <PortalAccessGate
              slug={slug}
              urlToken={urlToken}
              onSessionEstablished={handleSessionEstablished}
              onPortalUnavailable={handlePortalUnavailable}
            />
          )}

          {accessGateState === "authenticated" && sessionJwt && portalConfig && survey && (
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
                showLogo={appearance.branding.showLogo}
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
                    // Navigation button alignment. SurveyJS hides inactive nav
                    // actions with `.sv-action--hidden` (zero-size but still a
                    // flex item); drop them from layout so alignment is exact.
                    "& .sd-body__navigation .sv-action--hidden": {
                      display: "none",
                    },
                    // A lone visible button (single-page portal = Submit only,
                    // or first page = Next only) is centered.
                    "& .sd-action-bar.sd-body__navigation": {
                      justifyContent: "center",
                    },
                    // When both Previous and a forward action (Next/Complete)
                    // are visible (multi-page middle/last pages), split them:
                    // Previous on the bottom-left, the forward action (Next or
                    // Submit) on the bottom-right.
                    "& .sd-action-bar.sd-body__navigation:has(#sv-nav-prev:not(.sv-action--hidden)):has(#sv-nav-next:not(.sv-action--hidden)), & .sd-action-bar.sd-body__navigation:has(#sv-nav-prev:not(.sv-action--hidden)):has(#sv-nav-complete:not(.sv-action--hidden))":
                      {
                        justifyContent: "space-between",
                      },
                  }}
                >
                  {/*
                   * SurveyJS-driven multi-page flow (Requirement 11.3).
                   * Replaces the legacy hard-coded
                   * destination → path → metadata → uploader stack. The custom
                   * questions thread the selected destination, current path, and
                   * metadata through `survey.data` (Requirements 7.3 / 7.5 /
                   * 11.4) — the page no longer drives that state. The provider
                   * supplies the live `mode: "public"` runtime (real API + i18n-ignore
                   * Uppy) and wires `onSessionExpired` so a mid-flow expiry
                   * resets to the gate (Requirement 15.2).
                   */}
                  <PortalRuntimeContext.Provider value={runtimeValue}>
                    {currentPageTitle && (
                      <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
                        {currentPageTitle}
                      </Typography>
                    )}
                    <Survey model={survey} />
                  </PortalRuntimeContext.Provider>
                </Box>
                {/*
                 * Footer (Requirements 12.12 / 12.13 / 12.14):
                 *   - Admin-authored `footerHtml` renders (DOMPurify-
                 *     sanitized) when non-empty.
                 *   - "Powered by MediaLake" renders when
                 *     `showPoweredBy === true`. When both are absent, // i18n-ignore
                 *     skip the footer container entirely so the card
                 *     ends cleanly on the survey body.
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
