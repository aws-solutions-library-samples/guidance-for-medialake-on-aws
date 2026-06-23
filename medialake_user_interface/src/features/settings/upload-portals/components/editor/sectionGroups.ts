import type { EditorSection, ValidationError } from "../../stores/usePortalEditorStore";

/**
 * The two scopes the editor sidebar groups its sections under. These mirror
 * the two reusable artifacts a portal can be built from:
 *
 *   - `"appearance"` → the visual style a **Theme** persists. This is exactly
 *     the `PortalAppearance` shape (`{ mode, colors, typography, layout,
 *     branding, content }`), so the sections that edit those slices live here.
 *   - `"structure"`  → everything a **Template** layers on top of appearance:
 *     the structural keys copied from a template (`accessMode`, file limits,
 *     etc.) plus the deep-cloned `pages`, `metadataFields`, and
 *     `destinations`.
 *
 * Keeping the grouping here (rather than inline in the sidebar) gives the
 * sidebar, the page-level "focus first error" logic, and the unit tests a
 * single definition to share.
 */
export type SectionGroupKey = "appearance" | "structure";

/**
 * Canonical group → section mapping. Section order within each group follows
 * the authoring order used elsewhere in the editor: branding/content first,
 * then the visual style slices; pages/fields first in structure (so fields are
 * configured next to where they are placed), then destinations/access/limits.
 */
export const SECTION_GROUPS: ReadonlyArray<{
  key: SectionGroupKey;
  /** Plain-text header label. The feature is not i18n-wired, so labels are inline. */
  label: string;
  /** One-line helper that ties the group to its reusable artifact. */
  helper: string;
  sections: ReadonlyArray<EditorSection>;
}> = [
  {
    key: "appearance",
    label: "Appearance",
    helper: "Saved as a Theme. Also included in Templates.",
    sections: ["branding", "content", "appearance", "typography", "layout"],
  },
  {
    key: "structure",
    label: "Structure",
    helper: "Saved as a Template, along with Appearance.",
    sections: ["pages", "fields", "destinations", "access", "metadata"],
  },
];

/**
 * Flattened section order across all groups. Used to assert (in tests) that no
 * section is orphaned or duplicated, and available to any consumer that needs
 * the grouped display order as a flat list.
 */
export const ALL_GROUPED_SECTIONS: ReadonlyArray<EditorSection> = SECTION_GROUPS.flatMap(
  (group) => group.sections
);

/**
 * Resolve the group a section belongs to. Every {@link EditorSection} is
 * guaranteed to live in exactly one group (enforced by the sectionGroups
 * tests), so the lookup is total.
 */
export const groupOfSection = (section: EditorSection): SectionGroupKey => {
  const group = SECTION_GROUPS.find((g) => g.sections.includes(section));
  if (!group) {
    // Defensive: only reachable if a new EditorSection is added to the union
    // without being placed in a group. The unit test catches this at build/CI
    // time, but throwing here makes the omission loud rather than silent.
    throw new Error(`Section "${section}" is not assigned to any sidebar group`);
  }
  return group.key;
};

/**
 * Sum the validation errors across every section in a group, for the rollup
 * badge rendered on the group header. Mirrors the per-section count the
 * sidebar already shows, so a collapsed group still signals it contains
 * problems.
 */
export const countGroupErrors = (
  groupKey: SectionGroupKey,
  validationErrors: Partial<Record<EditorSection, ValidationError[]>>
): number => {
  const group = SECTION_GROUPS.find((g) => g.key === groupKey);
  if (!group) return 0;
  return group.sections.reduce((sum, section) => sum + (validationErrors[section]?.length ?? 0), 0);
};
