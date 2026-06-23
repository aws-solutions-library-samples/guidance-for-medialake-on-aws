import React, { useEffect, useMemo, useRef } from "react";
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
import type { SectionGroupKey } from "./sectionGroups";
import { SECTION_GROUPS, countGroupErrors, groupOfSection } from "./sectionGroups";
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
 * Human-readable label per section. Grouping and order live in
 * {@link SECTION_GROUPS} (the single source of truth); this record only maps a
 * section key to the text shown on its accordion header.
 *
 * `"appearance"` is labelled "Colors" rather than "Appearance" so it does not
 * collide with the enclosing "Appearance" group header — the section edits
 * `appearance.mode` + `appearance.colors`, so "Colors" reads clearly. The
 * section *key* is unchanged, so validation buckets and focus ids are
 * unaffected.
 */
const SECTION_LABELS: Record<EditorSection, string> = {
  branding: "Branding",
  content: "Content",
  pages: "Pages & Workflow",
  fields: "Field Configuration",
  appearance: "Colors",
  typography: "Typography",
  layout: "Layout",
  access: "Access Control",
  destinations: "Destinations",
  metadata: "Upload Limits & File Settings",
};

/**
 * PortalEditorSidebar
 *
 * Left-hand sidebar for the portal visual editor. Sections are organized under
 * two group accordions that mirror the reusable artifacts:
 *
 *   - "Appearance" → branding, content, colors, typography, layout. This is
 *     exactly the `PortalAppearance` shape a **Theme** persists.
 *   - "Structure"  → pages, fields, destinations, access, upload limits. These
 *     are the structural pieces a **Template** layers on top of appearance.
 *
 * Behavior preserved from the flat version:
 *   - Exactly one section is expanded at a time, driven by `activeSection`.
 *   - Expanding a different section calls `onSectionChange(newSection)`.
 *   - Re-clicking the open section collapses it (local `isActiveCollapsed`).
 *   - Each section header shows an error-colored Chip with its error count,
 *     and the body shows an Alert listing the issues.
 *   - Focus moves into the newly-active section body on `activeSection` change.
 *
 * Added for grouping:
 *   - Each group can be collapsed/expanded independently. The group that owns
 *     the active section is force-expanded whenever the active section moves
 *     into it (so the active section can never be hidden behind a collapsed
 *     group), while still letting the user collapse it manually afterwards.
 *   - Each group header shows a rollup `Chip` summing its sections' errors so a
 *     collapsed group still signals it contains problems.
 */
const PortalEditorSidebar: React.FC<PortalEditorSidebarProps> = ({
  activeSection,
  onSectionChange,
}) => {
  // Single sidebar-level subscription to validation errors so every section
  // header and every group rollup can read counts without each subscribing.
  const validationErrors = usePortalEditorStore((s) => s.validationErrors);

  // Local "manually collapsed" flag for the currently-active section. The store
  // tracks exactly one `activeSection`, but the user can click the expand arrow
  // on the open section to collapse it without switching sections. Expanding
  // any section clears it; switching sections resets it (effect below).
  const [isActiveCollapsed, setIsActiveCollapsed] = React.useState(false);

  useEffect(() => {
    setIsActiveCollapsed(false);
  }, [activeSection]);

  // --- Group expand/collapse state ---------------------------------------
  const activeGroupKey = useMemo(() => groupOfSection(activeSection), [activeSection]);

  const [expandedGroups, setExpandedGroups] = React.useState<Record<SectionGroupKey, boolean>>(
    () => {
      const initialGroup = groupOfSection(activeSection);
      return SECTION_GROUPS.reduce(
        (acc, group) => {
          acc[group.key] = group.key === initialGroup;
          return acc;
        },
        {} as Record<SectionGroupKey, boolean>
      );
    }
  );

  // Whenever the active section moves into a different group (e.g. validation
  // auto-focus or deep link jumps to a section in a collapsed group), force
  // that group open so the active section is visible. Manual collapses of the
  // active group afterwards are still honored because this only re-runs when
  // `activeGroupKey` itself changes.
  useEffect(() => {
    setExpandedGroups((prev) => ({ ...prev, [activeGroupKey]: true }));
  }, [activeGroupKey]);

  const handleGroupToggle =
    (groupKey: SectionGroupKey) => (_event: React.SyntheticEvent, isExpanded: boolean) => {
      setExpandedGroups((prev) => ({ ...prev, [groupKey]: isExpanded }));
    };

  // Track whether this is the first render. On mount we do NOT pull focus into
  // the sidebar — the parent page owns initial focus placement. We only react
  // to subsequent `activeSection` changes driven by the user opening a section.
  const isFirstRenderRef = useRef(true);

  // Focus the first focusable element inside the newly-active AccordionDetails
  // when `activeSection` changes (Requirement 16.17). Expansion is animated, so
  // we wait one animation frame to let the content commit before querying it.
  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    const moveFocus = () => {
      const panel = document.getElementById(`portal-editor-section-${activeSection}-content`);
      if (!panel) return;
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
      setTimeout(moveFocus, 0);
    }
  }, [activeSection]);

  const handleChange =
    (section: EditorSection) => (_event: React.SyntheticEvent, isExpanded: boolean) => {
      if (isExpanded) {
        // Expanding: always make the target visible. Switch the active section
        // when it differs; re-expanding the active section just clears the
        // manual-collapse flag.
        setIsActiveCollapsed(false);
        if (section !== activeSection) {
          onSectionChange(section);
        }
      } else if (section === activeSection) {
        // Collapse request on the open section: hide it so the expand arrow
        // works both ways.
        setIsActiveCollapsed(true);
      }
    };

  /**
   * Render the body for a given section. All ten sections are wired.
   *
   * Note on raw Markdown exposure: `ContentSection` renders every text field
   * through `RichTextEditor`, which is HTML-native via Tiptap. No code path in
   * this sidebar surfaces raw Markdown syntax (Requirement 8.13).
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
        return <FieldConfigurationSection />;
      case "pages":
        return <PagesWorkflowSection />;
      default: {
        // Exhaustiveness check: a new section key added to the union but not
        // here is a TypeScript error.
        const _exhaustive: never = section;
        return null;
      }
    }
  };

  /** Render a single section accordion (one row inside a group). */
  const renderSection = (section: EditorSection): React.ReactNode => {
    const label = SECTION_LABELS[section];
    const sectionErrors = validationErrors[section];
    const errorCount = sectionErrors?.length ?? 0;

    return (
      <Accordion
        key={section}
        expanded={activeSection === section && !isActiveCollapsed}
        onChange={handleChange(section)}
        disableGutters
        square
        elevation={0}
      >
        <AccordionSummary
          expandIcon={<ExpandMoreIcon />}
          aria-controls={`portal-editor-section-${section}-content`}
          id={`portal-editor-section-${section}-header`}
        >
          <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%" }}>
            <Typography variant="subtitle2">{label}</Typography>
            {errorCount > 0 && (
              <Chip
                label={errorCount}
                color="error"
                size="small"
                aria-label={`${errorCount} ${errorCount === 1 ? "error" : "errors"} in ${label}`}
              />
            )}
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
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
          {renderSectionBody(section)}
        </AccordionDetails>
      </Accordion>
    );
  };

  return (
    <Box
      role="complementary"
      aria-label="Portal editor settings"
      sx={{ height: "100%", overflowY: "auto" }}
    >
      {SECTION_GROUPS.map(({ key: groupKey, label, helper, sections }) => {
        const groupErrors = countGroupErrors(groupKey, validationErrors);
        return (
          <Accordion
            key={groupKey}
            expanded={expandedGroups[groupKey]}
            onChange={handleGroupToggle(groupKey)}
            disableGutters
            square
            elevation={0}
            sx={{ "&:not(:last-of-type)": { borderBottom: 1, borderColor: "divider" } }}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls={`portal-editor-group-${groupKey}-content`}
              id={`portal-editor-group-${groupKey}-header`}
              sx={{ bgcolor: "action.hover" }}
            >
              <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%", pr: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="overline" sx={{ display: "block", lineHeight: 1.4 }}>
                    {label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                    {helper}
                  </Typography>
                </Box>
                {groupErrors > 0 && (
                  <Chip
                    label={groupErrors}
                    color="error"
                    size="small"
                    aria-label={`${groupErrors} ${
                      groupErrors === 1 ? "error" : "errors"
                    } in ${label}`}
                    sx={{ ml: "auto" }}
                  />
                )}
              </Stack>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              {sections.map((sectionKey) => renderSection(sectionKey))}
            </AccordionDetails>
          </Accordion>
        );
      })}
    </Box>
  );
};

export { PortalEditorSidebar };
export default PortalEditorSidebar;
