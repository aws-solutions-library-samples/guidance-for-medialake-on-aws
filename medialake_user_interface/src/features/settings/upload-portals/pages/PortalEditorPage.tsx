import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Snackbar,
  Stack,
  Typography,
} from "@mui/material";
import { useBlocker, useNavigate, useParams, useSearchParams } from "react-router";

import {
  useCreatePortal,
  useGetPortal,
  useUpdatePortal,
  useUploadPortalLogo,
} from "@/api/hooks/usePortals";
import { useGetTemplate } from "@/api/hooks/useTemplates";
import { useGetTheme } from "@/api/hooks/useThemes";
import { useGetConnectors } from "@/api/hooks/useConnectors";
import type { Portal, PortalDestination, PortalTemplate, PortalTheme } from "@/api/types/api.types";
import { usePortalEditorStore } from "../stores/usePortalEditorStore";
import {
  describeDestination,
  findMissingConnectorDestinations,
} from "../utils/findMissingConnectorDestinations";
import PortalEditorToolbar from "../components/editor/PortalEditorToolbar";
import PortalEditorThemeTemplateActions from "../components/editor/PortalEditorThemeTemplateActions";
import PortalEditorSidebar from "../components/editor/PortalEditorSidebar";
import PortalEditorPreview from "../components/editor/PortalEditorPreview";
import { readFileAsBase64 } from "../utils/readFileAsBase64";
import type { EditorSection, PreviewMode } from "../stores/usePortalEditorStore";

/**
 * Sidebar section order used by the first-error-focus routine. Matches
 * {@link PortalEditorSidebar}'s rendering order (Requirement 9.5). We pick
 * the first section in this list that has one or more errors, open its
 * accordion, and move keyboard focus to its header button.
 */
const SECTION_ORDER: EditorSection[] = [
  "branding",
  "content",
  "pages",
  "fields",
  "appearance",
  "typography",
  "layout",
  "access",
  "destinations",
  "metadata",
];

/** Cycle order for the Cmd/Ctrl+Shift+P preview-mode shortcut. */
const PREVIEW_MODE_CYCLE: PreviewMode[] = ["desktop", "tablet", "mobile"];

interface ToastState {
  open: boolean;
  message: string;
  severity: "success" | "error";
}

/**
 * Extract a string URL or S3 key from the logo-upload response. The
 * backend currently returns the raw body axios-unwrapped, which looks like
 * `{ success, data: { logoS3Key } }` but may eventually return // i18n-ignore
 * `logoUrl` directly. We try both keys and fall back to the top-level
 * shape for forward compatibility. Matches the extraction logic used in
 * `BrandingSection` so the two upload paths stay consistent.
 */
const extractLogoUrlFromResponse = (response: unknown): string | undefined => {
  if (!response || typeof response !== "object") return undefined;
  const inner = (response as { data?: Record<string, unknown> }).data;
  const candidateKeys = ["logoUrl", "logoS3Key"] as const;
  if (inner && typeof inner === "object") {
    for (const key of candidateKeys) {
      if (typeof inner[key] === "string") return inner[key] as string;
    }
  }
  const top = response as Record<string, unknown>;
  for (const key of candidateKeys) {
    if (typeof top[key] === "string") return top[key] as string;
  }
  return undefined;
};

/**
 * PortalEditorPage
 *
 * Full-page portal visual editor. Renders a three-panel layout inside the
 * existing `AppLayout` outlet:
 *
 *   ┌─────────────────────────────────────────────────────────────────┐
 *   │ PortalEditorToolbar  [sticky top, height 56px]                  │
 *   ├──────────────────────┬──────────────────────────────────────────┤
 *   │ PortalEditorSidebar  │ PortalEditorPreview                      │
 *   │ width: 360px         │ flex: 1                                  │
 *   │ overflow-y: auto     │                                          │
 *   └──────────────────────┴──────────────────────────────────────────┘
 *
 * Data loading & store initialization
 * -----------------------------------
 * - In edit mode, `useGetPortal(id)` fetches the portal from the backend.
 *   When the portal arrives we call `store.initialize(portal)` exactly once
 *   so the sidebar/preview pick up the deep-merged appearance.
 * - In create mode `store.initialize()` seeds defaults.
 *
 * Save / Publish
 * --------------
 * - Both handlers call `store.validate()` first; on failure they open the
 *   first failing section and move focus to its accordion header button
 *   (Requirements 10.7, 16.14).
 * - In edit mode any staged `logoFile` is uploaded immediately via
 *   `useUploadPortalLogo` and the returned URL is written back onto the
 *   payload + the store.
 * - In create mode the logo upload is deferred until after the portal is
 *   created (we need the new portalId); the upload fires before the
 *   navigation to `/:id/edit`.
 * - Publish is Save + `isActive = true` (Requirement 10.4). // i18n-ignore
 *
 * Unsaved-changes guard
 * ---------------------
 * - React Router v7 `useBlocker` pops a confirmation dialog on in-app
 *   navigation when `isDirty === true` (Requirement 10.12). // i18n-ignore
 * - `beforeunload` covers full-page navigation and tab close.
 *
 * Keyboard shortcuts (Requirements 10.13, 10.14)
 * ----------------------------------------------
 * - `Cmd/Ctrl+S` → Save.
 * - `Cmd/Ctrl+Shift+P` → cycle preview mode (desktop → tablet → mobile → …).
 *
 * Preview in new tab (Requirement 10.15)
 * -------------------------------------
 * - `window.open("/p/" + slug, "_blank", "noopener,noreferrer")` when a // i18n-ignore
 *   slug exists and we are not in create mode.
 */
const PortalEditorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isCreateMode = !id || id === "new";
  const duplicateId = isCreateMode ? searchParams.get("duplicate") ?? "" : "";
  // Create-from-template / apply-theme seeding (task 17.3). When the create
  // route carries `?template=<id>` and/or `?theme=<id>`, we fetch the full
  // entities and seed the editor via `store.initializeFromSources` (snapshot,
  // copy-on-create — Requirements 16.5, 17.4). These are ignored outside
  // create mode.
  const seedTemplateId = isCreateMode ? searchParams.get("template") ?? "" : "";
  const seedThemeId = isCreateMode ? searchParams.get("theme") ?? "" : "";

  // Skip the request in create mode by passing an empty string (the hook is
  // gated on `enabled: !!id`).
  const portalQuery = useGetPortal(isCreateMode ? "" : id ?? "");
  const portal = portalQuery.data?.data as Portal | undefined;

  // Fetch the source portal when duplicating.
  const duplicateQuery = useGetPortal(duplicateId);
  const duplicatePortal = duplicateQuery.data?.data as Portal | undefined;

  // Fetch the seed template/theme when creating-from (task 17.3).
  const seedTemplateQuery = useGetTemplate(seedTemplateId);
  const seedTemplate = seedTemplateQuery.data?.data as PortalTemplate | undefined;
  const seedThemeQuery = useGetTheme(seedThemeId);
  const seedTheme = seedThemeQuery.data?.data as PortalTheme | undefined;

  // Current connector list (task 17.4). Used AFTER create-from-template
  // seeding to detect seeded destinations whose `connectorId` no longer
  // resolves to a real connector. We always run the query (the hook is
  // cheap and shared) but only act on it in create-from-template mode.
  const connectorsQuery = useGetConnectors();

  const initialize = usePortalEditorStore((s) => s.initialize);
  const initializeFromSources = usePortalEditorStore((s) => s.initializeFromSources);
  const acknowledgeRestoredDraft = usePortalEditorStore((s) => s.acknowledgeRestoredDraft);
  const hasRestoredDraft = usePortalEditorStore((s) => s.hasRestoredDraft);
  const portalName = usePortalEditorStore((s) => (s.portalData?.name as string | undefined) ?? "");
  const isDirty = usePortalEditorStore((s) => s.isDirty);
  const isSaving = usePortalEditorStore((s) => s.isSaving);
  const activeSection = usePortalEditorStore((s) => s.activeSection);
  const setActiveSection = usePortalEditorStore((s) => s.setActiveSection);
  const previewMode = usePortalEditorStore((s) => s.previewMode);
  const setPreviewMode = usePortalEditorStore((s) => s.setPreviewMode);
  const historyIndex = usePortalEditorStore((s) => s.historyIndex);
  const historyLength = usePortalEditorStore((s) => s.history.length);
  const undo = usePortalEditorStore((s) => s.undo);
  const redo = usePortalEditorStore((s) => s.redo);

  // Subscribe to the seeded destinations so the missing-connector check
  // (task 17.4) re-runs when the admin reselects a connector. Typed loosely
  // on the store, so narrow back to `PortalDestination[]` here.
  const destinations = usePortalEditorStore(
    (s) => (s.portalData?.destinations as PortalDestination[] | undefined) ?? undefined
  );

  const canUndo = historyIndex > 0;
  const canRedo = historyIndex < historyLength - 1;

  const createPortal = useCreatePortal();
  const updatePortal = useUpdatePortal();
  const uploadLogo = useUploadPortalLogo();

  const [toast, setToast] = useState<ToastState>({
    open: false,
    message: "",
    severity: "success",
  });

  /**
   * Create-from-template missing-connector warning (task 17.4 / Requirement
   * 17.8). Holds the friendly names of seeded destinations whose `connectorId`
   * is not present in the current connector list, or `null` when there is
   * nothing to warn about. This is a NON-BLOCKING, informational prompt — it
   * never blocks Save and never mutates the seeded snapshot. The admin can
   * dismiss it; reselecting a connector recomputes it automatically.
   */
  const [missingConnectorNames, setMissingConnectorNames] = useState<string[] | null>(null);

  // `useBlocker` needs a stable predicate; capture the latest `isDirty`
  // through a ref so the predicate never has to be re-registered just
  // because the dirty flag flipped.
  const isDirtyRef = useRef(isDirty);
  isDirtyRef.current = isDirty;

  useEffect(() => {
    if (isCreateMode) {
      // Handle duplicate mode: when a `?duplicate=portalId` param is present,
      // fetch that portal and seed the store with its data (minus portalId).
      if (duplicateId && duplicatePortal) {
        const cloned = { ...duplicatePortal } as unknown as Parameters<typeof initialize>[0];
        initialize(cloned);
        // Clear the portalId and adjust name/slug for the copy
        usePortalEditorStore.getState().updatePortalData({
          portalId: undefined,
          name: (duplicatePortal.name || "") + " (Copy)",
          slug: (duplicatePortal.slug || "") + "-copy",
          // Clear the logo file since it can't be cloned
          logoFile: null,
        });
        usePortalEditorStore.setState({ isDirty: true });
        return;
      }

      // Handle create-from-template / apply-theme seeding (task 17.3). We wait
      // until any requested source has resolved before seeding so the snapshot
      // is complete. `initializeFromSources` resolves the appearance layering
      // (DEFAULT → template/its theme → selected theme) and deep-clones the
      // template structure (snapshot, no live link — Property 11).
      //
      // Task 17.4 (create-from-template MISSING-CONNECTOR warning) runs in a
      // SEPARATE effect below, AFTER this seeding: it compares each seeded
      // destination's `connectorId` against the current connector list and
      // surfaces a non-blocking warning. The check is intentionally NOT done
      // here so it can also re-run when the admin reselects a connector or the
      // connector query resolves late — and so seeding stays purely a snapshot
      // (no mutation of the seeded destinations).
      if (seedTemplateId || seedThemeId) {
        const templateReady = !seedTemplateId || !!seedTemplate;
        const themeReady = !seedThemeId || !!seedTheme;
        if (!templateReady || !themeReady) {
          // Still loading the source(s); don't seed defaults yet.
          return;
        }
        initializeFromSources({
          template: seedTemplate,
          theme: seedTheme,
        });
        return;
      }

      // In create mode a restored draft applies only if its `portalId`
      // is falsy (i.e. it was created for `/new`). We detect that by
      // reading the current store state synchronously — if a draft is
      // live AND has no `portalId`, keep it; otherwise seed defaults.
      const state = usePortalEditorStore.getState();
      const draftIsForCreate =
        state.hasRestoredDraft &&
        (state.portalData?.portalId === undefined ||
          state.portalData?.portalId === null ||
          state.portalData?.portalId === "");
      if (!draftIsForCreate) {
        initialize();
      }
      return;
    }
    if (portal) {
      // If the persisted draft is for the portal we just fetched, keep
      // it (the unsaved edits win over a fresh server fetch, which is
      // the whole point of draft persistence — Requirement 14.7). For a
      // different portal, the fresh server payload overwrites the draft
      // via `initialize(portal)`, and `initialize` clears
      // `hasRestoredDraft` so the banner disappears.
      const state = usePortalEditorStore.getState();
      const draftMatchesPortal =
        state.hasRestoredDraft &&
        typeof state.portalData?.portalId === "string" &&
        state.portalData.portalId === portal.portalId;
      if (draftMatchesPortal) return;
      initialize(portal as unknown as Parameters<typeof initialize>[0]);
    }
  }, [
    isCreateMode,
    portal,
    initialize,
    initializeFromSources,
    duplicateId,
    duplicatePortal,
    seedTemplateId,
    seedTemplate,
    seedThemeId,
    seedTheme,
  ]);

  // ---- Create-from-template missing-connector warning (task 17.4) ------
  //
  // Requirement 17.8: a Template captures each destination's `connectorId`
  // verbatim, so a Portal seeded from a Template can reference a connector
  // that does not exist in this environment (templates may be authored in a
  // different account/region, or the connector may have been deleted). After
  // seeding, we compare each seeded destination's `connectorId` against the
  // CURRENT connector list and surface a NON-BLOCKING warning naming the
  // affected destination(s), prompting the admin to reselect before saving.
  //
  // Snapshot semantics are unchanged (Property 11): this effect is purely
  // informational — it never mutates the seeded destinations or clears a
  // `connectorId`; it only computes a list of names for the banner.
  //
  // We gate on the connectors query having RESOLVED (`isSuccess`) so we don't
  // false-positive while the list is still fetching. Reselecting a connector
  // updates `destinations`, which re-runs this effect and clears the warning
  // once every destination resolves.
  const fromTemplate = isCreateMode && !!seedTemplateId;
  const connectorsResolved = connectorsQuery.isSuccess;
  const availableConnectorIds = connectorsQuery.data?.data?.connectors;

  useEffect(() => {
    // Only meaningful when creating from a template and the connector list
    // has resolved. Outside that path, ensure no stale warning lingers.
    if (!fromTemplate || !connectorsResolved) {
      return;
    }

    const connectorIds = (availableConnectorIds ?? []).map((connector) => connector.id);
    const missing = findMissingConnectorDestinations(destinations, connectorIds);

    if (missing.length === 0) {
      setMissingConnectorNames(null);
      return;
    }

    const names = missing.map((destination) =>
      describeDestination(destination, (destinations ?? []).indexOf(destination))
    );
    setMissingConnectorNames(names);
  }, [fromTemplate, connectorsResolved, availableConnectorIds, destinations]);

  // ---- Focus management (task 5.14) ------------------------------------
  //
  // On first mount, move keyboard focus to the Back button so keyboard
  // users land in a predictable, recoverable place (Requirement 16.16).
  // The toolbar mounts synchronously, so we look the button up by its
  // accessible name (`aria-label="Back to portals"`) immediately after
  // the first paint. Running once via an empty dep array keeps the focus
  // shift from stomping on later user interactions (e.g. opening the
  // color popover triggers a sidebar re-render but shouldn't steal
  // focus).
  useEffect(() => {
    const backButton = document.querySelector<HTMLButtonElement>(
      'button[aria-label="Back to portals"]'
    );
    backButton?.focus();
  }, []);

  const showError = !isCreateMode && portalQuery.isError;
  const showLoading = !isCreateMode && portalQuery.isLoading;

  // ---- Save / Publish --------------------------------------------------

  /**
   * Move focus to the first sidebar section that has validation errors.
   * The accordion must expand first; we flip `activeSection`, then on the
   * next animation frame grab the accordion header button by id and call
   * `.focus()` on it. Gracefully no-ops when no errors are present (the
   * normal path for successful validation).
   */
  const focusFirstErrorSection = useCallback(() => {
    const { validationErrors } = usePortalEditorStore.getState();
    const firstErrorSection = SECTION_ORDER.find(
      (section) => (validationErrors[section]?.length ?? 0) > 0
    );
    if (!firstErrorSection) return;

    usePortalEditorStore.getState().setActiveSection(firstErrorSection);

    // Accordion expansion is driven by `activeSection` in the React tree;
    // a single animation frame is enough for the new render to commit and
    // the matching `AccordionSummary` button to be mountable in the DOM.
    const focusHeader = () => {
      const header = document.getElementById(`portal-editor-section-${firstErrorSection}-header`);
      if (header) {
        (header as HTMLElement).focus();
      }
    };
    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(focusHeader);
    } else {
      // jsdom / SSR fallback: microtask is late enough for the re-render.
      setTimeout(focusHeader, 0);
    }
  }, []);

  /**
   * Shared save pipeline. `publish = true` forces `isActive: true` on the // i18n-ignore
   * payload so Publish is "Save + activate" (Requirement 10.4).
   */
  const runSave = useCallback(
    async ({ publish }: { publish: boolean }) => {
      const store = usePortalEditorStore.getState();
      if (!store.validate()) {
        // Auto-expand + focus the first failing section (task 5.9).
        focusFirstErrorSection();

        // Build a descriptive toast message listing the specific issues.
        const { validationErrors } = usePortalEditorStore.getState();
        const totalErrors = Object.values(validationErrors).reduce(
          (sum, errs) => sum + (errs?.length ?? 0),
          0
        );
        const errorSummary = Object.entries(validationErrors)
          .filter(([, errs]) => errs && errs.length > 0)
          .map(([, errs]) => errs!.map((e) => e.message))
          .flat()
          .slice(0, 3) // Show at most 3 in the toast
          .join(" • ");
        const suffix = totalErrors > 3 ? ` (+${totalErrors - 3} more)` : "";

        setToast({
          open: true,
          message: `${errorSummary}${suffix}`,
          severity: "error",
        });
        return;
      }

      store.setSaving(true);

      // Build the payload after validation so `validationErrors` is empty.
      const payload = store.getPayload();
      if (publish) {
        payload.isActive = true;
      }

      // Stash the logo file reference *now* so subsequent store writes
      // (e.g. `updateLogoUrl`) don't interfere with our branching.
      const logoFile = store.portalData?.logoFile ?? null;
      const portalIdFromStore =
        typeof store.portalData?.portalId === "string" ? store.portalData.portalId : undefined;

      try {
        if (isCreateMode) {
          // Create flow: POST first, then optionally upload the logo against
          // the newly-minted portalId, then navigate into the edit route.
          const response = await createPortal.mutateAsync(payload);
          const created = response.data;
          const newId = created.portalId;

          let logoUploadFailed = false;
          if (logoFile && newId) {
            try {
              const { base64, contentType } = await readFileAsBase64(logoFile);
              const uploadResponse = await uploadLogo.mutateAsync({
                id: newId,
                base64Image: base64,
                contentType,
              });
              const resolvedUrl = extractLogoUrlFromResponse(uploadResponse);
              if (resolvedUrl) {
                usePortalEditorStore.getState().updateLogoUrl(resolvedUrl);
              }
              // Clear the stashed file either way so the editor doesn't
              // re-upload on the next Save.
              usePortalEditorStore.getState().setLogoFile(null);
            } catch {
              // The logo-upload mutation already surfaces its own modal via
              // `useUploadPortalLogo`'s `onError`. We keep the create flow
              // alive and tell the user the portal was saved but the logo
              // upload needs to be retried. Do NOT fall through to the
              // success toast below.
              logoUploadFailed = true;
              setToast({
                open: true,
                message:
                  "Portal created, but the logo upload failed. Retry from the Branding section.",
                severity: "error",
              });
            }
          }

          usePortalEditorStore.getState().markClean();
          // Synchronously clear the ref so `useBlocker`'s predicate sees
          // the clean state *before* the navigate call triggers it.
          // Without this, React hasn't re-rendered yet and the ref still
          // holds `true`, causing the unsaved-changes dialog to flash.
          isDirtyRef.current = false;
          if (!logoUploadFailed) {
            setToast({
              open: true,
              message: publish ? "Portal published." : "Portal created.",
              severity: "success",
            });
          }
          navigate(`/settings/upload-portals/${newId}/edit`);
        } else {
          // Edit flow: upload the logo first so the returned URL can be
          // baked into the payload. Keeps the API surface
          // transactional-ish from the server's perspective.
          if (logoFile && portalIdFromStore) {
            try {
              const { base64, contentType } = await readFileAsBase64(logoFile);
              const uploadResponse = await uploadLogo.mutateAsync({
                id: portalIdFromStore,
                base64Image: base64,
                contentType,
              });
              const resolvedUrl = extractLogoUrlFromResponse(uploadResponse);
              if (resolvedUrl) {
                payload.logoUrl = resolvedUrl;
                usePortalEditorStore.getState().updateLogoUrl(resolvedUrl);
              }
              usePortalEditorStore.getState().setLogoFile(null);
            } catch {
              // Abort the save — the user will see the logo upload's own
              // error modal and can retry.
              return;
            }
          }

          const updateId = portalIdFromStore ?? id ?? "";
          if (!updateId) {
            // Defensive: neither the editor store nor the route param gave
            // us a portal id. Calling updatePortal with an empty id would
            // send an invalid request and surface a confusing 404. Surface
            // a clear error to the user instead.
            setToast({
              open: true,
              message: "Cannot save portal: missing portal id.",
              severity: "error",
            });
            return;
          }
          await updatePortal.mutateAsync({ id: updateId, data: payload });
          usePortalEditorStore.getState().markClean();
          isDirtyRef.current = false;
          setToast({
            open: true,
            message: publish ? "Portal published." : "Changes saved.",
            severity: "success",
          });
        }
      } catch (error) {
        // `useCreatePortal` / `useUpdatePortal` already render error modals
        // for non-409 cases; 409s throw `new Error("Slug already exists")`
        // in the mutationFn. Surface both as a local toast so the
        // editor-level UX is consistent.
        const message =
          error instanceof Error && error.message ? error.message : "Failed to save portal.";
        setToast({ open: true, message, severity: "error" });
      } finally {
        usePortalEditorStore.getState().setSaving(false);
      }
    },
    [createPortal, focusFirstErrorSection, id, isCreateMode, navigate, updatePortal, uploadLogo]
  );

  const handleSave = useCallback(() => {
    void runSave({ publish: false });
  }, [runSave]);

  const handlePublish = useCallback(() => {
    void runSave({ publish: true });
  }, [runSave]);

  const handleBack = () => navigate("/settings/upload-portals");

  const handlePreviewInNewTab = useCallback(() => {
    if (isCreateMode) return;
    const slug = usePortalEditorStore.getState().portalData?.slug;
    if (!slug || typeof slug !== "string") return;
    window.open(`/p/${slug}`, "_blank", "noopener,noreferrer");
  }, [isCreateMode]);

  // ---- Keyboard shortcuts (task 5.11) ---------------------------------

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMeta = event.metaKey || event.ctrlKey;
      if (!isMeta) return;

      // Cmd/Ctrl+Shift+P → cycle preview mode.
      if (event.shiftKey && (event.key === "P" || event.key === "p")) {
        event.preventDefault();
        const current = usePortalEditorStore.getState().previewMode;
        const currentIndex = PREVIEW_MODE_CYCLE.indexOf(current);
        const nextIndex = currentIndex === -1 ? 0 : (currentIndex + 1) % PREVIEW_MODE_CYCLE.length;
        usePortalEditorStore.getState().setPreviewMode(PREVIEW_MODE_CYCLE[nextIndex]);
        return;
      }

      // Cmd/Ctrl+Shift+Z → redo
      if (event.shiftKey && (event.key === "z" || event.key === "Z")) {
        event.preventDefault();
        usePortalEditorStore.getState().redo();
        return;
      }

      // Cmd/Ctrl+Z → undo
      if (!event.shiftKey && (event.key === "z" || event.key === "Z")) {
        event.preventDefault();
        usePortalEditorStore.getState().undo();
        return;
      }

      // Cmd/Ctrl+S → save
      if (!event.shiftKey && (event.key === "s" || event.key === "S")) {
        event.preventDefault();
        handleSave();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleSave]);

  // ---- beforeunload (task 5.10 full-page navigation) ------------------

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirtyRef.current) return;
      // The "standard" opt-in to the native dialog is to call
      // `preventDefault()` and set `returnValue`. Modern Chrome ignores
      // the string, but Firefox still honors it in some flows, so set
      // both.
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  // ---- useBlocker in-app guard (task 5.10) -----------------------------

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirtyRef.current && currentLocation.pathname !== nextLocation.pathname
  );

  const handleToastClose = useCallback((_event?: React.SyntheticEvent | Event, reason?: string) => {
    // Ignore `clickaway` dismissals so a misclick doesn't swallow the
    // error message while the user is reading it.
    if (reason === "clickaway") return;
    setToast((prev) => ({ ...prev, open: false }));
  }, []);

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      {/*
       * Screen-reader-only live region announcing "Saving..." / "Saved"
       * so assistive tech picks up save state without visual noise
       * (Requirement 16.18). The Snackbar below covers explicit
       * success/error messaging via MUI `Alert` (implicit role="alert",
       * announced as aria-live="assertive"); this region is a quieter
       * polite announcer for the in-flight state only.
       */}
      <Box
        aria-live="polite"
        sx={{
          position: "absolute",
          left: -9999,
          width: 1,
          height: 1,
          overflow: "hidden",
        }}
      >
        {isSaving ? "Saving..." : ""}
      </Box>
      {/* Sticky top toolbar — 56px, real PortalEditorToolbar. */}
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 1,
          flexShrink: 0,
          borderBottom: 1,
          borderColor: "divider",
          backgroundColor: "background.paper",
        }}
      >
        <PortalEditorToolbar
          portalName={portalName}
          isCreateMode={isCreateMode}
          isDirty={isDirty}
          isSaving={isSaving}
          onSave={handleSave}
          onPublish={handlePublish}
          onPreviewInNewTab={handlePreviewInNewTab}
          onBack={handleBack}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={undo}
          onRedo={redo}
          extraActions={
            <PortalEditorThemeTemplateActions
              onNotify={(message, severity) => setToast({ open: true, message, severity })}
            />
          }
        />
      </Box>

      {/*
       * Restored-unsaved-changes banner (Requirement 14.7).
       *
       * Rendered immediately below the toolbar (above the sidebar +
       * preview region) whenever `persist` rehydrated a non-empty draft
       * on mount and the user hasn't dismissed it yet. The `onClose`
       * callback dismisses the banner only — the draft itself keeps
       * auto-persisting until a successful save clears it.
       */}
      {hasRestoredDraft ? (
        <Box sx={{ flexShrink: 0, px: 2, pt: 1 }}>
          <Alert severity="info" onClose={acknowledgeRestoredDraft} role="status">
            Restored unsaved changes from your last session.
          </Alert>
        </Box>
      ) : null}

      {/*
       * Create-from-template missing-connector warning (Requirement 17.8 /
       * task 17.4).
       *
       * Shown when a Portal was seeded from a Template and one or more seeded
       * destinations reference a `connectorId` that is not in the current
       * connector list. It is NON-BLOCKING: the admin can still edit and save
       * — this only prompts them to reselect a connector for the named
       * destination(s) before saving. Reselecting a valid connector (or
       * dismissing) clears the banner. The seeded snapshot is never mutated by
       * this warning.
       */}
      {missingConnectorNames && missingConnectorNames.length > 0 ? (
        <Box sx={{ flexShrink: 0, px: 2, pt: 1 }}>
          <Alert severity="warning" role="alert" onClose={() => setMissingConnectorNames(null)}>
            {missingConnectorNames.length === 1
              ? `The connector for "${missingConnectorNames[0]}" isn't available in this environment. Reselect a connector for this destination before saving.`
              : `The connectors for these destinations aren't available in this environment: ${missingConnectorNames
                  .map((name) => `"${name}"`)
                  .join(", ")}. Reselect a connector for each before saving.`}
          </Alert>
        </Box>
      ) : null}

      {/* Body: sidebar + preview, OR loading/error fallback in edit mode. */}
      {showError ? (
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: 4,
          }}
        >
          <Stack spacing={2} alignItems="center" sx={{ maxWidth: 480 }}>
            {/* i18n-ignore */}
            <Typography variant="h6">Failed to load portal</Typography>
            <Typography variant="body2" color="text.secondary" align="center">
              We couldn't load this portal. Check your connection and try again, or return to the
              portals list.
            </Typography>
            <Stack direction="row" spacing={1}>
              <Button variant="outlined" onClick={() => navigate("/settings/upload-portals")}>
                Back
              </Button>
              <Button
                variant="contained"
                onClick={() => {
                  void portalQuery.refetch();
                }}
              >
                Retry
              </Button>
            </Stack>
          </Stack>
        </Box>
      ) : showLoading ? (
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: 4,
          }}
        >
          <CircularProgress />
        </Box>
      ) : (
        <Box
          sx={{
            display: "flex",
            flexDirection: "row",
            flex: 1,
            minHeight: 0,
          }}
        >
          {/* Left sidebar — 360px wide, vertically scrollable. */}
          <Box
            sx={{
              width: 360,
              minWidth: 360,
              flexShrink: 0,
              borderRight: 1,
              borderColor: "divider",
              backgroundColor: "background.paper",
            }}
          >
            <PortalEditorSidebar activeSection={activeSection} onSectionChange={setActiveSection} />
          </Box>

          {/* Right preview — fills remaining width. */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <PortalEditorPreview previewMode={previewMode} onPreviewModeChange={setPreviewMode} />
          </Box>
        </Box>
      )}

      {/* Unsaved-changes confirmation dialog (task 5.10). */}
      <Dialog
        open={blocker.state === "blocked"}
        onClose={() => {
          if (blocker.state === "blocked") blocker.reset();
        }}
        aria-labelledby="portal-editor-unsaved-dialog-title"
        aria-describedby="portal-editor-unsaved-dialog-description"
      >
        {/* i18n-ignore */}
        <DialogTitle id="portal-editor-unsaved-dialog-title">Unsaved changes</DialogTitle>
        <DialogContent>
          <DialogContentText id="portal-editor-unsaved-dialog-description">
            You have unsaved changes. Leave anyway?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              if (blocker.state === "blocked") blocker.reset();
            }}
          >
            Cancel
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => {
              if (blocker.state === "blocked") blocker.proceed();
            }}
          >
            Leave
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save/Publish status toast. */}
      <Snackbar
        open={toast.open}
        autoHideDuration={6000}
        onClose={handleToastClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          onClose={handleToastClose}
          severity={toast.severity}
          sx={{ width: "100%" }}
          variant="filled"
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default PortalEditorPage;
