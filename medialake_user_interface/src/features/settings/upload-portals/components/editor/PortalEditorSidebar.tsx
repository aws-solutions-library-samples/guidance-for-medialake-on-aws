import React, { useEffect, useRef } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import type { EditorSection } from "../../stores/usePortalEditorStore";
import { usePortalEditorStore } from "../../stores/usePortalEditorStore";
import AccessControlSection from "./sections/AccessControlSection";
import AppearanceSection from "./sections/AppearanceSection";
import BrandingSection from "./sections/BrandingSection";
import ContentSection from "./sections/ContentSection";
import DestinationsSection from "./sections/DestinationsSection";
import FieldConfigurationSection from "./sections/FieldConfigurationSection";
import LayoutSection from "./sections/LayoutSection";
import MetadataSection from "./sections/MetadataSection";
import PagesWorkflowSection from "./sections/PagesWorkflowSection";
import TypographySection from "./sections/TypographySection";

/**
 * Props for {@link PortalEditorSidebar}.
 *
 * Shape mirrors design.md § "Key TypeScript Interfaces" exactly so later
 * phases can plug real section bodies in without reshaping the API.
 */
export interface PortalEditorSidebarProps {
  activeSection: EditorSection;
  onSectionChange: (section: EditorSection) => void;
}

/**
 * Ordered section list for the sidebar accordion.
 *
 * Order: Branding → Content → Pages & Workflow → Field Configuration →
 * Appearance → Typography → Layout → Access Control → Destinations →
 * Upload Limits & File Settings. "Field Configuration" sits directly under
 * "Pages & Workflow" so fields are configured next to where they are placed,
 * and "Upload Limits & File Settings" (the former "Metadata & Limits") holds the
 * upload-limit controls.
 */
const SECTIONS: { key: EditorSection; label: string }[] = [
  { key: "branding", label: "Branding" },
  { key: "content", label: "Content" },
  { key: "pages", label: "Pages & Workflow" },
  { key: "fields", label: "Field Configuration" },
  { key: "appearance", label: "Appearance" },
  { key: "typography", label: "Typography" },
  { key: "layout", label: "Layout" },
  { key: "access", label: "Access Control" },
  { key: "destinations", label: "Destinations" },
  { key: "metadata", label: "Upload Limits & File Settings" },
];

/**
 * PortalEditorSidebar
 *
 * Left-hand accordion sidebar for the portal visual editor. Renders the
 * eight sections in the canonical order and enforces single-expansion
 * behavior driven by `activeSection` (Requirement 9.6).
 *
 * Behavior:
 *   - Exactly one section is expanded at any time, determined by
 *     `activeSection`.
 *   - Expanding a different section calls `onSectionChange(newSection)`.
 *   - Collapse requests on the currently active section are ignored so the
 *     sidebar always has one open panel.
 *   - All eight section bodies are wired: Branding, Content, Appearance,
 *     Typography, Layout, Access Control, Destinations, and Metadata &
 *     Limits each render their respective section component.
 *   - When `store.validationErrors[section]` has one or more entries, the
 *     accordion header renders a small MUI `Chip color="error"` showing // i18n-ignore
 *     the error count. Auto-expand of the first failing section is wired
 *     in task 5.9 (validation-failure handling) — this component just
 *     renders the badge (Requirement 17.4).
 *
 * Layout:
 *   The parent page controls the sidebar width (360px per design.md). This
 *   component only provides a scrollable vertical container so long section
 *   bodies don't spill into the preview pane.
 */
const PortalEditorSidebar: React.FC<PortalEditorSidebarProps> = ({
  activeSection,
  onSectionChange,
}) => {
  // Subscribe to validation errors once at the sidebar level so every
  // accordion header can render its own badge without each section
  // individually subscribing. This is a single Zustand subscription that
  // re-runs all eight header renders on change — cheap compared to
  // repeating the subscription inside each section.
  const validationErrors = usePortalEditorStore((s) => s.validationErrors);

  // Track whether this is the first render. On mount we do NOT pull focus
  // into the sidebar — the parent page owns initial focus placement
  // (currently the Back button, see `PortalEditorPage` task 5.14). We only
  // react to subsequent `activeSection` changes driven by the user
  // clicking a different accordion header.
  const isFirstRenderRef = useRef(true);

  // Focus the first focusable element inside the newly-active
  // AccordionDetails when `activeSection` changes (Requirement 16.17).
  // Accordion expansion is driven by the `expanded` prop and MUI animates
  // the details region, so we wait one animation frame to let the
  // content commit before querying it.
  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    const moveFocus = () => {
      const panel = document.getElementById(`portal-editor-section-${activeSection}-content`);
      if (!panel) return;
      // Standard focusable selectors — matches the web-accessibility
      // "tabbable elements" list (excluding `[tabindex="-1"]` which
      // participates in focus only programmatically).
      const focusable = panel.querySelector<HTMLElement>(
        [
          "input:not([disabled]):not([type='hidden'])",
          "select:not([disabled])",
          "textarea:not([disabled])",
          "button:not([disabled])",
          "a[href]",
          "[tabindex]:not([tabindex='-1'])",
          "[contenteditable='true']",
        ].join(", ")
      );
      focusable?.focus();
    };

    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(moveFocus);
    } else {
      // jsdom / SSR fallback: microtask is late enough for the re-render.
      setTimeout(moveFocus, 0);
    }
  }, [activeSection]);

  const handleChange =
    (section: EditorSection) => (_event: React.SyntheticEvent, isExpanded: boolean) => {
      // Only react to expand events. Ignoring collapse keeps exactly one
      // section open, which matches Requirement 9.6.
      if (isExpanded && section !== activeSection) {
        onSectionChange(section);
      }
    };

  /**
   * Render the body for a given section. All eight sections are fully
   * wired: Branding, Content, Appearance, Typography, Layout (Phase 2-3)
   * and Access Control, Destinations, Metadata & Limits (Phase 5).
   *
   * Note on raw Markdown exposure: `ContentSection` renders every text
   * field through `RichTextEditor`, which is HTML-native via Tiptap. No
   * code path in this sidebar surfaces raw Markdown syntax, which
   * satisfies Requirement 8.13.
   */
  const renderSectionBody = (section: EditorSection): React.ReactNode => {
    switch (section) {
      case "branding":
        return <BrandingSection />;
      case "content":
        return <ContentSection />;
      case "appearance":
        return <AppearanceSection />;
      case "typography":
        return <TypographySection />;
      case "layout":
        return <LayoutSection />;
      case "access":
        return <AccessControlSection />;
      case "destinations":
        return <DestinationsSection />;
      case "metadata":
        return <MetadataSection />;
      case "fields":
        // Field Configuration section: the metadata field builder (label /
        // type / required / choices). Sits under "Pages & Workflow" so fields
        // are configured next to where they are dragged onto pages.
        return <FieldConfigurationSection />;
      case "pages":
        // Pages & Workflow section: page CRUD/reorder, drag-and-drop field
        // placement, and uploader-page assignment. Wired in task 13.3. The
        // per-section validation Alert above this body surfaces structural
        // violations recorded under the "pages" bucket (Requirement 10.5).
        return <PagesWorkflowSection />;
      default: {
        // Exhaustiveness check: if a new section key is added to the union
        // but not to this switch, TypeScript will flag the missing arm.
        const _exhaustive: never = section;
        return null;
      }
    }
  };

  return (
    <Box
      role="complementary"
      aria-label="Portal editor settings"
      sx={{ height: "100%", overflowY: "auto" }}
    >
      {SECTIONS.map(({ key, label }) => {
        const sectionErrors = validationErrors[key];
        const errorCount = sectionErrors?.length ?? 0;
        return (
          <Accordion
            key={key}
            expanded={activeSection === key}
            onChange={handleChange(key)}
            disableGutters
            square
            elevation={0}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls={`portal-editor-section-${key}-content`}
              id={`portal-editor-section-${key}-header`}
            >
              <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%" }}>
                <Typography variant="subtitle2">{label}</Typography>
                {errorCount > 0 && (
                  <Chip
                    label={errorCount}
                    color="error"
                    size="small"
                    aria-label={`${errorCount} ${
                      errorCount === 1 ? "error" : "errors"
                    } in ${label}`}
                  />
                )}
              </Stack>
            </AccordionSummary>
            <AccordionDetails id={`portal-editor-section-${key}-content`}>
              {errorCount > 0 && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    {errorCount === 1 ? "1 issue to fix:" : `${errorCount} issues to fix:`}
                  </Typography>
                  <Stack component="ul" spacing={0.5} sx={{ m: 0, pl: 2 }}>
                    {sectionErrors!.map((err, idx) => (
                      <li key={idx}>
                        <Typography variant="body2">
                          <strong>{err.field}:</strong> {err.message}
                        </Typography>
                      </li>
                    ))}
                  </Stack>
                </Alert>
              )}
              {renderSectionBody(key)}
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Box>
  );
};

export { PortalEditorSidebar };
export default PortalEditorSidebar;
