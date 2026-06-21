import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Box,
  IconButton,
  Paper,
  ScopedCssBaseline,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import EditIcon from "@mui/icons-material/Edit";
import DOMPurify from "dompurify";

import { Model } from "survey-core";
import { Survey } from "survey-react-ui";
// SurveyJS default theme stylesheet. This is a global stylesheet import, which
// is acceptable here: the `ScopedCssBaseline` + scoped `createPortalTheme`
// still isolate the MUI chrome, while this base CSS makes the SurveyJS DOM
// render styled inside the preview frame.
import "survey-core/survey-core.min.css";

import type {
  PortalConfig,
  PortalPage,
  PortalPageElement,
} from "@/features/portal/types/portal.types";
import type { PortalDestination, PortalMetadataField } from "@/api/types/api.types";

import type { PortalAppearance } from "../../types/appearance.types";
import { createPortalTheme } from "../../utils/createPortalTheme";
import { usePortalEditorStore } from "../../stores/usePortalEditorStore";
// Req 6.1: the preview builds its schema EXCLUSIVELY through the shared
// `buildSurveyJson` + `registerPortalQuestions` — there is no alternative
// schema-building path. `slug` is the shared label→fieldKey slugifier used to
// synthesize the create-mode fallback page below.
import { buildSurveyJson, slug as slugifyLabel } from "../../shared/portalSurveyModel";
import { registerPortalQuestions } from "../../shared/registerPortalQuestions";
// Side-effect import: binds the four custom question React renderers (including
// the mock uploader used in `preview` mode) before any Survey is rendered. The
// module self-registers at import and the registration is idempotent.
import "../../shared/questions/registerPortalQuestionRenderers";
import { PortalRuntimeContext, type PortalRuntimeValue } from "../../shared/PortalRuntimeContext";

/**
 * Props for {@link PortalPreviewRenderer}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces". `appearance` and
 * `portalData` are passed by {@link PortalEditorPreview} (which applies
 * `useDeferredValue` to `appearance` and supplies mock fallbacks for
 * `metadataFields`/`destinations` in create mode). The multi-page `pages`
 * slice is read from the editor store directly so the preview re-renders as
 * soon as the page structure changes (Requirement 8.4).
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
 * Stable empty-pages reference. Returning a fresh `[]` from the zustand
 * selector on every render would change identity each call and thrash the
 * subscription; a module-level constant keeps the selection referentially
 * stable until the store actually holds pages.
 */
const EMPTY_PAGES: PortalPage[] = [];

/**
 * Determine whether a sanitized HTML string carries meaningful content.
 *
 * Mirrors the helper in {@link PortalHeader} so the admin preview and the
 * public page agree on when a cleared rich-text field (Tiptap emits
 * `<p></p>` / `<p><br></p>` / whitespace-only markup) should fall back to the
 * plain-text `name`. Strips tags and collapses entities/whitespace, while
 * still treating embedded media as content.
 */
const htmlHasContent = (html: string | undefined | null): boolean => {
  if (!html) return false;
  const text = html
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/\s+/g, "")
    .trim();
  if (text.length > 0) return true;
  return /<(img|video|iframe|svg|audio)\b/i.test(html);
};

/**
 * PortalPreviewRenderer
 *
 * Renders the live preview of the public upload-portal page. It builds the
 * shared SurveyJS schema via {@link buildSurveyJson} (Requirement 6.1) and
 * renders it through `survey-react-ui`'s `<Survey>` in DISPLAY (non-interactive)
 * mode with the mock uploader (Requirement 6.4), so the preview and the public
 * renderer stay in lockstep — both consume the SAME `buildSurveyJson` +
 * `registerPortalQuestions`, with no second schema path.
 *
 * Isolation layers (outside-in) are preserved from the previous mock so the
 * preview's theme / CSS never leaks into the surrounding editor chrome:
 *   1. `<Box sx={{ all: "initial", display: "contents" }}>` — CSS reset
 *      boundary (Requirement 3.7).
 *   2. `<ThemeProvider theme={createPortalTheme(appearance)}>` — scoped MUI
 *      theme built from the appearance snapshot (Requirement 3.2).
 *   3. `<ScopedCssBaseline>` — baseline styles applied only within the preview
 *      subtree instead of globally.
 *   4. The card chrome (banner, header, footer) wrapping the SurveyJS body.
 *
 * The metadata form, drop zone, and submit button that the previous mock
 * hand-built are now rendered by the shared SurveyJS model: the uploader
 * question renders its preview-mode mock drop-zone (because the runtime context
 * `mode` is `"preview"`), and metadata fields / destination selectors / path
 * questions render their own preview-safe forms.
 *
 * HTML content (`titleHtml`, `descriptionHtml`, `footerHtml`) is still passed
 * through DOMPurify before injection via `dangerouslySetInnerHTML`, keeping
 * parity with the public renderer.
 */
const PortalPreviewRendererComponent: React.FC<PortalPreviewRendererProps> = ({
  appearance,
  portalData,
}) => {
  const theme = useMemo(() => createPortalTheme(appearance), [appearance]);

  // Read the multi-page structure straight from the editor store so a change
  // to the pages slice re-renders the preview immediately (Requirement 8.4).
  // The parent already defers `appearance`, keeping re-renders within 500ms.
  const pages = usePortalEditorStore(
    (s) => (s.portalData?.pages as PortalPage[] | undefined) ?? EMPTY_PAGES
  );
  const portalSlug = usePortalEditorStore((s) => (s.portalData?.slug as string | undefined) ?? "");
  const updatePage = usePortalEditorStore((s) => s.updatePage);

  // Sanitize the chrome HTML once per change. DOMPurify is synchronous and
  // fast, but memoizing keeps the render cheap when only a color changes.
  const sanitizedTitle = useMemo(
    () =>
      htmlHasContent(appearance.content.titleHtml)
        ? DOMPurify.sanitize(appearance.content.titleHtml ?? "")
        : "",
    [appearance.content.titleHtml]
  );
  const sanitizedDescription = useMemo(
    () =>
      htmlHasContent(appearance.content.descriptionHtml)
        ? DOMPurify.sanitize(appearance.content.descriptionHtml ?? "")
        : "",
    [appearance.content.descriptionHtml]
  );
  const sanitizedFooter = useMemo(
    () =>
      htmlHasContent(appearance.content.footerHtml)
        ? DOMPurify.sanitize(appearance.content.footerHtml ?? "")
        : "",
    [appearance.content.footerHtml]
  );

  const hasTitleHtml = sanitizedTitle.length > 0;
  const hasDescriptionHtml = sanitizedDescription.length > 0;
  const hasFooterHtml = sanitizedFooter.length > 0;

  const shouldRenderBanner =
    appearance.branding.bannerHeight > 0 && !!appearance.branding.bannerUrl;

  const cardElevation = CARD_SHADOW_ELEVATION[appearance.layout.cardShadow];

  // When the portal has no pages yet (create mode, before the Pages & Workflow
  // section seeds any), synthesize a single representative page so the preview
  // still shows a useful form. This only shapes the INPUT config; the schema is
  // still derived exclusively through `buildSurveyJson` (Requirement 6.1).
  const effectivePages = useMemo<PortalPage[]>(() => {
    if (pages.length > 0) return pages;
    const elements: PortalPageElement[] = [
      { kind: "destination-selector" },
      ...(portalData.metadataFields ?? []).map(
        (field): PortalPageElement => ({
          kind: "metadata-field",
          fieldKey: slugifyLabel(field.label),
        })
      ),
      { kind: "uploader" },
    ];
    return [{ pageNumber: 1, title: "", elements }];
  }, [pages, portalData.metadataFields]);

  // Build the PortalConfig that feeds the shared schema builder + runtime
  // context. Destinations/metadata fields come from `portalData` (the parent's
  // mock-fallback-aware slices); appearance is the deferred snapshot; pages are
  // the live store slice (or the synthesized fallback above).
  const config = useMemo<PortalConfig>(
    () => ({
      slug: portalSlug,
      name: portalData.name,
      logoUrl: portalData.logoUrl,
      accessMode: "public",
      tokenBypassesPassphrase: false,
      isActive: true,
      metadataFields: portalData.metadataFields as unknown as PortalConfig["metadataFields"],
      destinations: portalData.destinations as unknown as PortalConfig["destinations"],
      structuredPathMode: false,
      captchaEnabled: false,
      pages: effectivePages,
      appearance,
    }),
    [portalSlug, portalData, effectivePages, appearance]
  );

  // Derive the SurveyJS model from the shared builder and render it in DISPLAY
  // (non-interactive) mode (Requirement 6.4). `registerPortalQuestions` is
  // idempotent; calling it here guarantees the custom question MODELS exist
  // even if this module's renderer side-effect import was tree-shaken in some
  // build path.
  const survey = useMemo(() => {
    registerPortalQuestions();
    const model = new Model(buildSurveyJson(config));
    // Interactive preview: render the standard inputs (dropdown, radio,
    // checkboxes, tags, yes/no, text, number) as fully operable so the admin
    // can try the choices before publishing. The custom questions (uploader,
    // destination picker, path browser/builder) still render their own
    // non-functional mock because they branch on the runtime `mode: "preview"`.
    model.mode = "edit";
    // The card chrome already renders the portal title; suppress the survey's
    // own title so it is not duplicated.
    model.showTitle = false;
    // We render our own editable page-title heading above the body, so hide
    // SurveyJS's per-page title/description to avoid duplication.
    model.showPageTitles = false;
    // This is a throwaway preview model: never let it actually "complete"
    // (there is no live session), and don't let required-field validation
    // block page navigation while the admin is just clicking around.
    model.showCompleteButton = false;
    model.ignoreValidation = true;
    model.onCompleting.add((_sender, options) => {
      options.allow = false;
    });
    return model;
  }, [config]);

  // Track the survey's current page index so the editable heading targets the
  // page actually shown in the preview (multi-page surveys show one at a time).
  const [currentPageNo, setCurrentPageNo] = useState(0);
  useEffect(() => {
    setCurrentPageNo(survey.currentPageNo);
    const handler = (sender: Model) => setCurrentPageNo(sender.currentPageNo);
    survey.onCurrentPageChanged.add(handler);
    return () => survey.onCurrentPageChanged.remove(handler);
  }, [survey]);

  // The portal page that maps to the survey's current page. `buildSurveyJson`
  // sorts pages by ascending `pageNumber`, so the survey's page index aligns
  // with the sorted effectivePages order.
  const sortedPages = useMemo(
    () => [...effectivePages].sort((a, b) => a.pageNumber - b.pageNumber),
    [effectivePages]
  );
  const currentPage = sortedPages[currentPageNo] ?? sortedPages[0];
  // Only real (store-backed) pages are editable; the synthesized create-mode
  // fallback page has no counterpart to write back to.
  const canEditPageTitle = pages.length > 0 && currentPage !== undefined;

  // Inline edit state for the current page's title.
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  const beginTitleEdit = useCallback(() => {
    if (!canEditPageTitle) return;
    setTitleDraft(currentPage?.title ?? "");
    setIsEditingTitle(true);
  }, [canEditPageTitle, currentPage]);

  const commitTitleEdit = useCallback(() => {
    setIsEditingTitle(false);
    if (!currentPage) return;
    const trimmed = titleDraft.trim();
    if (trimmed === (currentPage.title ?? "")) return;
    updatePage(currentPage.pageNumber, { title: trimmed });
  }, [titleDraft, currentPage, updatePage]);

  const cancelTitleEdit = useCallback(() => {
    setIsEditingTitle(false);
    setTitleDraft(currentPage?.title ?? "");
  }, [currentPage]);

  // Preview runtime: non-interactive, no live session. The uploader question
  // branches on `mode === "preview"` to render its mock drop-zone.
  const runtimeValue = useMemo<PortalRuntimeValue>(
    () => ({
      mode: "preview",
      slug: portalSlug,
      sessionJwt: null,
      config,
    }),
    [portalSlug, config]
  );

  return (
    // Layer 1: CSS reset boundary. `display: contents` removes the box from
    // layout so the preview frame sizing rules still apply to the card.
    <Box sx={{ all: "initial", display: "contents" }}>
      {/* Layer 2: scoped MUI theme. */}
      <ThemeProvider theme={theme}>
        {/* Layer 3: scoped baseline styles. */}
        <ScopedCssBaseline>
          {/* Layer 4: the card chrome. */}
          <Paper
            elevation={cardElevation}
            sx={{
              maxWidth: `${appearance.layout.cardMaxWidth}px`,
              width: "100%",
              mx: "auto",
              overflow: "hidden",
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
                {appearance.branding.showLogo &&
                  (portalData.logoUrl ? (
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
                  ))}

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

              {/* Editable page-title heading. Bound to the survey's current
                  page; click (or the pencil) to rename, committing through
                  `updatePage`. Kept OUT of the aria-hidden survey box below so
                  it remains operable/announced. */}
              {canEditPageTitle && (
                <Box sx={{ mb: 2 }}>
                  {isEditingTitle ? (
                    <TextField
                      autoFocus
                      fullWidth
                      size="small"
                      variant="standard"
                      value={titleDraft}
                      onChange={(e) => setTitleDraft(e.target.value)}
                      onBlur={commitTitleEdit}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          commitTitleEdit();
                        } else if (e.key === "Escape") {
                          e.preventDefault();
                          cancelTitleEdit();
                        }
                      }}
                      aria-label={`Title for page ${currentPage.pageNumber}`}
                    />
                  ) : (
                    <Stack direction="row" alignItems="center" spacing={0.5}>
                      <Typography
                        variant="h6"
                        component="h2"
                        sx={{ cursor: "text" }}
                        onDoubleClick={beginTitleEdit}
                        // i18n-ignore
                        title="Double-click to rename"
                      >
                        {currentPage.title || "Untitled page"}
                      </Typography>
                      <Tooltip
                        // i18n-ignore
                        title="Rename page"
                      >
                        <IconButton
                          size="small"
                          aria-label={`Rename page ${currentPage.pageNumber}`}
                          onClick={beginTitleEdit}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  )}
                </Box>
              )}

              {/* Body: the shared SurveyJS model rendered in interactive
                  (edit) mode so the admin can actually try dropdowns, radios,
                  checkboxes, tags, and the yes/no toggle before publishing.
                  The custom questions (uploader, destination picker, path
                  questions) still render their non-functional mock because they
                  branch on the runtime `mode: "preview"`. This subtree is NOT i18n-ignore
                  aria-hidden — the controls are operable, so they must remain in
                  the accessibility tree. */}
              <Box
                sx={{
                  mb: hasFooterHtml || appearance.branding.showPoweredBy ? 3 : 0,
                  // Navigation button alignment (mirrors the public renderer).
                  // SurveyJS hides inactive nav actions with `.sv-action--hidden`
                  // (zero-size but still a flex item); drop them from layout so
                  // alignment math is exact.
                  "& .sd-body__navigation .sv-action--hidden": {
                    display: "none",
                  },
                  // A lone visible button (first page = Next only; last page =
                  // Previous only) is centered.
                  "& .sd-action-bar.sd-body__navigation": {
                    justifyContent: "center",
                  },
                  // When both Previous and a forward action (Next/Complete) are
                  // visible (middle pages), group them at the bottom-right.
                  "& .sd-action-bar.sd-body__navigation:has(#sv-nav-prev:not(.sv-action--hidden)):has(#sv-nav-next:not(.sv-action--hidden)), & .sd-action-bar.sd-body__navigation:has(#sv-nav-prev:not(.sv-action--hidden)):has(#sv-nav-complete:not(.sv-action--hidden))":
                    {
                      justifyContent: "flex-end",
                    },
                }}
              >
                <PortalRuntimeContext.Provider value={runtimeValue}>
                  <Survey model={survey} />
                </PortalRuntimeContext.Provider>
              </Box>

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
 * `useDeferredValue` + `useMemo` boundary, but `React.memo` still spares the
 * expensive theme/schema work on unrelated editor re-renders (e.g. sidebar
 * accordion state). The internal store subscription to the `pages` slice still
 * re-renders this component when the page structure changes.
 */
export const PortalPreviewRenderer = React.memo(PortalPreviewRendererComponent);

export default PortalPreviewRenderer;
