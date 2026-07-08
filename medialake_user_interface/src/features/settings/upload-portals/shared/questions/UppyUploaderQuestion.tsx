import { useEffect, useMemo, useRef } from "react";
import * as React from "react";

import type { Question, SurveyModel } from "survey-core";
import { ReactQuestionFactory } from "survey-react-ui";

import { Alert, Box, Typography } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";

import PortalUploader from "@/features/portal/components/PortalUploader";
import type { PortalConfig, PortalDestination } from "@/features/portal/types/portal.types";
import { PORTAL_DEFAULT_ALLOWED_FILE_TYPES } from "@/features/portal/constants";

import { DEFAULT_PORTAL_APPEARANCE } from "../../constants/appearanceDefaults";
import type { PortalAppearanceContent } from "../../types/appearance.types";
import { deepMerge } from "../../utils/deepMerge";
import {
  CURRENT_PATH_KEY,
  SELECTED_DESTINATION_KEY,
  UPLOAD_IN_PROGRESS_KEY,
  UPLOAD_SESSION_ID_KEY,
  UPLOADED_FILE_COUNT_KEY,
  collectMetadataValues,
  usePortalRuntime,
} from "../PortalRuntimeContext";
import { PORTAL_QUESTION_TYPES, registerPortalQuestions } from "../registerPortalQuestions";
import { useSurveyValue } from "./questionHelpers";

/**
 * Marker value written into `survey.data[question.name]` once an upload has
 * completed. SurveyJS treats a non-empty array as a non-empty answer, so a
 * required uploader question only counts as "answered" — and survey completion
 * is only unblocked — after at least one upload finishes (Requirement 5.8 /
 * 7.7). The element is intentionally opaque: the unchanged {@link PortalUploader}
 * owns the uploaded S3 keys internally and exposes no JS completion callback, so
 * the wrapper records a truthy completion marker rather than the key list.
 */
const UPLOAD_COMPLETE_MARKER: readonly string[] = ["uploaded"];

/**
 * CSS class MUI applies to a success-severity `Alert`. {@link PortalUploader}
 * renders exactly one such alert (its `successMessage`) when its internal Uppy
 * instance fires `complete`. Observing that alert appear in the wrapped subtree
 * is the only non-invasive completion signal available without modifying
 * `PortalUploader`.
 */
const MUI_ALERT_SUCCESS_CLASS = "MuiAlert-colorSuccess";

/**
 * Resolve the appearance `content` block for the current runtime config,
 * deep-merged onto {@link DEFAULT_PORTAL_APPEARANCE} so a portal without a saved
 * appearance still renders the baseline copy/styling (mirrors the fallback in
 * `UploadPortalPage`). Pure given its input.
 */
function resolveAppearanceContent(config: PortalConfig | null): PortalAppearanceContent {
  if (!config?.appearance) return DEFAULT_PORTAL_APPEARANCE.content;
  const merged = deepMerge(
    structuredClone(DEFAULT_PORTAL_APPEARANCE) as unknown as Record<string, unknown>,
    config.appearance as unknown as Record<string, unknown>
  ) as unknown as { content: PortalAppearanceContent };
  return merged.content;
}

/**
 * Non-interactive drop-zone placeholder rendered in `preview` mode. It mimics
 * the live uploader's drop area and submit button using the configured
 * appearance copy, but spins up NO Uppy instance and makes NO API calls — it is
 * purely presentational so the admin live-preview stays cheap and side-effect
 * free.
 */
function MockUploaderDropZone({
  content,
}: {
  content: PortalAppearanceContent;
}): React.JSX.Element {
  const radius =
    content.buttonRounding === "square" ? 0 : content.buttonRounding === "pill" ? "9999px" : 1;

  return (
    <Box
      aria-hidden
      data-testid="portal-mock-uploader"
      sx={{ display: "flex", flexDirection: "column", gap: 2 }}
    >
      <Box
        sx={{
          border: "2px dashed",
          borderColor: "divider",
          borderRadius: 1,
          minHeight: 200,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 1,
          p: 3,
          color: "text.secondary",
          textAlign: "center",
          userSelect: "none",
        }}
      >
        <CloudUploadIcon sx={{ fontSize: 48, opacity: 0.6 }} />
        <Typography variant="body2">
          {content.dropZoneText || DEFAULT_PORTAL_APPEARANCE.content.dropZoneText}
        </Typography>
      </Box>

      <Box
        component="div"
        role="presentation"
        sx={{
          alignSelf: "stretch",
          textAlign: "center",
          py: 1,
          px: 2,
          borderRadius: radius,
          bgcolor: content.buttonStyle === "text" ? "transparent" : "action.disabledBackground",
          border: content.buttonStyle === "outlined" ? "1px solid" : "none",
          borderColor: "divider",
          color: "text.secondary",
          fontWeight: 500,
        }}
      >
        {(content.submitButtonText && content.submitButtonText.trim()) ||
          DEFAULT_PORTAL_APPEARANCE.content.submitButtonText}
      </Box>
    </Box>
  );
}

/**
 * Live (public-mode) uploader. Wraps the existing {@link PortalUploader} — its
 * Uppy instance, `UploadQueueTable`, and `ConflictResolutionDialog` are reused
 * verbatim (Requirement 7.8); only the props now come from `survey.data` +
 * {@link usePortalRuntime} instead of `UploadPortalPage` local state.
 *
 * "Answered only after a completed upload" (Requirements 5.8 / 7.7): a scoped
 * `MutationObserver` watches the wrapped subtree for `PortalUploader`'s success
 * alert (rendered on Uppy `complete`) and, the first time it appears, writes the
 * completion marker into the survey so the required uploader question becomes
 * answered and Complete is unblocked. The wrapper triggers NO upload itself —
 * the single Upload action stays owned by `PortalUploader`, so navigation never
 * fires an extra upload.
 */
function LiveUploader({
  question,
  survey,
  destination,
  currentPath,
  metadata,
}: {
  question: Question;
  survey: SurveyModel;
  destination: PortalDestination;
  currentPath: string;
  metadata: Record<string, string>;
}): React.JSX.Element {
  const rt = usePortalRuntime();
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Guards the one-time marker write so repeated DOM mutations are no-ops.
  const markedRef = useRef(false);

  const content = useMemo(() => resolveAppearanceContent(rt.config), [rt.config]);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    const markAnswered = () => {
      if (markedRef.current) return;
      if (!node.querySelector(`.${MUI_ALERT_SUCCESS_CLASS}`)) return;
      markedRef.current = true;
      // Non-empty array → SurveyJS sees the required uploader as answered.
      survey.setValue(question.name, [...UPLOAD_COMPLETE_MARKER]);
    };

    // Catch a success alert already present (e.g. on re-mount after navigation).
    markAnswered();

    const observer = new MutationObserver(markAnswered);
    observer.observe(node, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [survey, question]);

  return (
    <div ref={containerRef}>
      <PortalUploader
        portalSlug={rt.slug}
        sessionJwt={rt.sessionJwt as string}
        destination={destination}
        currentPath={currentPath}
        metadataFields={metadata}
        maxFileSizeBytes={rt.config?.maxFileSizeBytes}
        maxFilesPerSession={rt.config?.maxFilesPerSession}
        onSessionExpired={() => rt.onSessionExpired?.()}
        useCaptchaIntegration={rt.config?.captchaEnabled}
        submitButtonText={content.submitButtonText}
        successMessage={content.successMessage}
        dropZoneText={content.dropZoneText}
        onSessionChange={(sessionId) => survey.setValue(UPLOAD_SESSION_ID_KEY, sessionId)}
        onUploadedCountChange={(count) => survey.setValue(UPLOADED_FILE_COUNT_KEY, count)}
        onUploadingChange={(uploading) => survey.setValue(UPLOAD_IN_PROGRESS_KEY, uploading)}
        allowedFileTypes={
          // Tri-state: an UNSET (undefined) config falls back to the default
          // media allow-list (legacy portals created before this field
          // existed). An explicit value — including an EMPTY array — is honored
          // verbatim; `[]` flows to PortalUploader which then applies no Uppy
          // restriction, i.e. "allow any file type".
          rt.config?.allowedFileTypes === undefined
            ? [...PORTAL_DEFAULT_ALLOWED_FILE_TYPES]
            : rt.config.allowedFileTypes
        }
        buttonStyle={content.buttonStyle}
        buttonRounding={content.buttonRounding}
      />
    </div>
  );
}

/**
 * React renderer bound to the `portal-uppy-uploader` custom SurveyJS question
 * (see {@link PORTAL_QUESTION_TYPES.uploader}). SurveyJS instantiates this with
 * `{ question }`; the renderer reads cross-page upload state from `survey.data` // i18n-ignore
 * (the destination id under {@link SELECTED_DESTINATION_KEY}, the resolved path
 * under {@link CURRENT_PATH_KEY}) plus the collected metadata, and the live
 * runtime surface from {@link usePortalRuntime}.
 *
 *  - `preview` mode → renders {@link MockUploaderDropZone} (no Uppy, no API).
 *  - `public` mode  → resolves the selected destination from `runtime.config`
 *    and renders the live {@link PortalUploader}. If no destination has been
 *    selected yet (empty {@link SELECTED_DESTINATION_KEY}) it renders an inline
 *    notice instead of the uploader; the question's own `isRequired` rule keeps
 *    Complete blocked and preserves entered data (Requirement 15.1).
 */
export function UppyUploaderRenderer({ question }: { question: Question }): React.JSX.Element {
  const rt = usePortalRuntime();
  const survey = question.survey as SurveyModel;

  // Read the cross-page upload state REACTIVELY so the uploader re-renders when
  // the destination/path are resolved after mount (e.g. the auto-resolve below,
  // or a selector on an earlier page). A plain survey.getValue would not
  // re-render on a later reserved-key write.
  const destinationId = useSurveyValue<string>(survey, SELECTED_DESTINATION_KEY);
  const currentPath = useSurveyValue<string>(survey, CURRENT_PATH_KEY) ?? "";
  const metadata = collectMetadataValues(survey);

  // Resolve the chosen destination. When the portal has exactly one
  // destination and no explicit selector was placed on a page, auto-resolve it
  // so the uploader works without a (visually empty) destination-selector
  // question. A multi-destination portal still requires an explicit selection.
  const allDestinations = rt.config?.destinations ?? [];
  const effectiveDestinationId =
    destinationId ?? (allDestinations.length === 1 ? allDestinations[0].destinationId : undefined);
  const destination = allDestinations.find((d) => d.destinationId === effectiveDestinationId);

  // Seed the cross-page upload state for an AUTO-RESOLVED sole destination.
  // For a single-destination portal `buildSurveyJson` emits no
  // destination-selector question, so nothing else writes
  // `__selectedDestinationId` or resolves `__currentPath` from the destination
  // rootPath. Mirror DestinationSelectorRenderer's auto-select here (once) so
  // the path questions and the live uploader receive the resolved path. Only
  // runs when there is no explicit selection and the path is not yet resolved.
  const seededRef = useRef<string | null>(null);
  useEffect(() => {
    if (rt.mode !== "public") return;
    if (!effectiveDestinationId || destinationId) return;
    if (currentPath) return;
    if (seededRef.current === effectiveDestinationId) return;
    seededRef.current = effectiveDestinationId;
    survey.setValue(SELECTED_DESTINATION_KEY, effectiveDestinationId);
    rt.onDestinationChange?.(effectiveDestinationId);
  }, [rt, survey, effectiveDestinationId, destinationId, currentPath]);

  if (rt.mode === "preview") {
    return <MockUploaderDropZone content={resolveAppearanceContent(rt.config)} />;
  }

  if (!destination || !rt.sessionJwt) {
    // No destination resolved (or no live session): do not render the live
    // uploader. The required uploader value stays empty so completion is
    // blocked and the user can still go back to pick a destination.
    return (
      <Alert severity="warning" data-testid="portal-uploader-no-destination">
        Select an upload destination before uploading files.
      </Alert>
    );
  }

  return (
    <LiveUploader
      question={question}
      survey={survey}
      destination={destination}
      currentPath={currentPath}
      metadata={metadata}
    />
  );
}

/**
 * Module-level guard so the React renderer is registered with
 * {@link ReactQuestionFactory} exactly once, even across hot-module-replacement
 * or repeated imports from both render paths.
 */
let rendererRegistered = false;

/**
 * Register the `portal-uppy-uploader` React renderer with `survey-react-ui` and
 * ensure the underlying question MODELS are registered too.
 *
 * Idempotent (Requirements 7.2 / 15.4): the model registration delegates to the
 * already-idempotent {@link registerPortalQuestions}, and the renderer
 * registration is guarded by {@link rendererRegistered} plus a check against the
 * live factory so repeated calls are no-ops that never throw and leave exactly
 * one renderer per type.
 *
 * Runs at module init (call at the bottom of this file) so the renderer exists
 * before either render path builds a survey; also exported so callers can invoke
 * it explicitly — the guard makes doing both safe.
 */
export function registerUppyUploaderRenderer(): void {
  // Ensure the custom question MODELS exist (idempotent).
  registerPortalQuestions();

  if (rendererRegistered) return;
  if (ReactQuestionFactory.Instance.getAllTypes().indexOf(PORTAL_QUESTION_TYPES.uploader) === -1) {
    ReactQuestionFactory.Instance.registerQuestion(PORTAL_QUESTION_TYPES.uploader, (props) =>
      React.createElement(UppyUploaderRenderer, {
        // SurveyJS passes the live question model on `props.question`. The
        // factory types the creator arg as `string`, so cast through unknown.
        question: (props as unknown as { question: Question }).question,
        key: (props as unknown as { question: Question }).question.id,
      })
    );
  }
  rendererRegistered = true;
}

// Register at module init so the renderer exists before any survey renders.
registerUppyUploaderRenderer();
