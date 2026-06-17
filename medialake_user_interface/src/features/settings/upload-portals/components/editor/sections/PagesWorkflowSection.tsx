import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
  TextField,
} from "@mui/material";
import {
  Add as AddIcon,
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
  DragIndicator as DragIcon,
  Edit as EditIcon,
} from "@mui/icons-material";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type Announcements,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import type { PortalMetadataField, PortalPage, PortalPageElement } from "@/api/types/api.types";

import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";

/**
 * The four admin-selectable metadata field types that can be dragged from the
 * palette onto a page (Requirement 8.1d). Mirrors
 * {@link PortalMetadataField.type}.
 */
type FieldType = PortalMetadataField["type"];

const FIELD_TYPES: readonly { type: FieldType; label: string }[] = [
  { type: "text", label: "Text" },
  { type: "number", label: "Number" },
  { type: "select", label: "Dropdown" },
  { type: "radiogroup", label: "Radio Group" },
  { type: "checkbox", label: "Checkboxes" },
  { type: "tagbox", label: "Tags" },
  { type: "boolean", label: "Yes / No" },
] as const;

/**
 * Special role-bearing fields draggable from the palette. These are ordinary
 * field types pre-wired with an automation `role` the backend interprets at
 * upload time (see portal-metadata-automation-design.md). The "Collection
 * Picker" is a multi-select whose value the server resolves into the
 * `ml-collection-ids` directive against the portal's saved allow-list.
 */
const SPECIAL_FIELD_TYPES: readonly {
  type: FieldType;
  role: PortalMetadataField["role"];
  label: string;
}[] = [{ type: "tagbox", role: "collection-picker", label: "Collection Picker" }] as const;

/**
 * Stable empty-array defaults so the Zustand selectors return referentially
 * stable values when the slices are absent — unrelated store writes then do
 * not force a re-render of this section.
 */
const EMPTY_PAGES: readonly PortalPage[] = [];
const EMPTY_FIELDS: readonly PortalMetadataField[] = [];

/**
 * Slugify an admin-authored field label into the stable `fieldKey` that ties a
 * `metadata-field` page element back to its {@link PortalMetadataField}.
 *
 * Mirrors the identically-named helper in `usePortalEditorStore.ts` and
 * `shared/portalSurveyModel.ts`; duplicated as a tiny pure function so this
 * component does not import the store internals or `survey-core`.
 */
const slug = (label: string): string =>
  label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

/**
 * Metadata describing a drag source, attached to every draggable/sortable via
 * its `data` prop so {@link PagesWorkflowSection}'s `onDragEnd` can route the
 * interaction to the correct store action without inspecting the DOM.
 */
type DragMeta =
  | { type: "palette-item"; fieldType: FieldType; role?: PortalMetadataField["role"] }
  | { type: "field"; fieldKey: string; pageNumber: number; index: number }
  | { type: "page"; pageNumber: number; index: number };

/**
 * Metadata describing a drop target. `pageNumber` identifies the destination
 * page and `index` the insertion position within that page's `elements` array.
 *
 * - `field` — an existing field row; dropping resolves to that field's index.
 * - `page-container` — a page's field drop-zone; dropping appends after the
 *   last field (index = current field count's element index).
 * - `page` — a page sortable node; only used for page reordering.
 */
type DropMeta =
  | { type: "field"; fieldKey: string; pageNumber: number; index: number }
  | { type: "page-container"; pageNumber: number; index: number }
  | { type: "page"; pageNumber: number; index: number };

/** dnd-kit exposes the active/over `data` as `unknown`; narrow it safely. */
const asDragMeta = (data: unknown): DragMeta | null =>
  data && typeof (data as { type?: unknown }).type === "string" ? (data as DragMeta) : null;

const asDropMeta = (data: unknown): DropMeta | null =>
  data && typeof (data as { type?: unknown }).type === "string" ? (data as DropMeta) : null;

/**
 * Build a short, human-readable label for a drag source/drop target, used in
 * the live-region announcements (Requirement 8.7).
 */
const describeMeta = (meta: DragMeta | DropMeta | null): string => {
  if (!meta) return "item";
  switch (meta.type) {
    case "page":
    case "page-container":
      return `Page ${meta.pageNumber}`;
    case "field":
      return `field "${meta.fieldKey}"`;
    case "palette-item":
      return `new ${meta.fieldType} field`;
    default:
      return "item";
  }
};

/**
 * The two interaction modes the section supports, derived from the active drag
 * source so collision detection can ignore irrelevant droppables:
 *
 *   - `"page"`   — reordering page cards (only page sortable nodes matter);
 *   - `"field"`  — moving/creating a field (only field rows + page containers
 *                  matter; page sortable nodes are ignored so a field never
 *                  collides with the card chrome and silently no-ops).
 */
type DragMode = "page" | "field" | null;

export const dragModeFor = (meta: DragMeta | null): DragMode => {
  if (!meta) return null;
  if (meta.type === "page") return "page";
  return "field"; // "field" | "palette-item"
};

/**
 * Resolve the destination page + insertion index for a field/palette drag from
 * the `over` drop target.
 *
 * - over a `field` row → that field's page + its element index (insert before
 *   it), unless it is the dragged field moving DOWN within the same page, in
 *   which case the post-removal shift is corrected by the store's clamp; we
 *   pass the raw target index and let `reorderFieldWithinPage` splice it in.
 * - over a `page-container` → that page, appended after the last element.
 *
 * Returns `null` when the target is not a valid field drop target (e.g. a page
 * sortable node), so the caller can no-op cleanly.
 */
const resolveFieldDrop = (over: DropMeta | null): { pageNumber: number; index: number } | null => {
  if (!over) return null;
  if (over.type === "field") return { pageNumber: over.pageNumber, index: over.index };
  if (over.type === "page-container") return { pageNumber: over.pageNumber, index: over.index };
  return null;
};

// Re-export the drop resolver + meta types for unit testing the routing logic
// without driving a full jsdom drag (which dnd-kit's keyboard/pointer sensors
// can't reliably simulate under jsdom's no-layout environment).
export { resolveFieldDrop };
export type { DragMeta, DropMeta };

/**
 * A draggable field-type swatch in the palette. Uses `useDraggable` (not
 * sortable) because palette items are a drag *source* only — they are never
 * reordered and never act as a drop target.
 */
const PaletteItem: React.FC<{
  fieldType: FieldType;
  label: string;
  role?: PortalMetadataField["role"];
}> = ({ fieldType, label, role }) => {
  const data: DragMeta = useMemo(
    () => ({ type: "palette-item", fieldType, role }),
    [fieldType, role]
  );
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-${role ?? fieldType}`,
    data,
  });
  return (
    <Chip
      ref={setNodeRef}
      icon={<DragIcon />}
      label={label}
      variant="outlined"
      {...attributes}
      {...listeners}
      sx={{
        cursor: "grab",
        opacity: isDragging ? 0.4 : 1,
        "& .MuiChip-icon": { cursor: "grab" },
      }}
    />
  );
};

/**
 * A single sortable `metadata-field` element within a page. The drag handle is
 * the {@link DragIcon} button so that focusing/activating it (pointer or
 * keyboard) starts the drag, while the rest of the row stays interactive.
 *
 * The label is inline-editable: clicking the edit (pencil) button — or pressing
 * Enter/Space while it is focused — swaps the read-only label for a text field.
 * Committing the edit calls {@link onRename}, which routes to the store's
 * `renameField` action so the field's `label` and every referencing page
 * element's `fieldKey` are updated atomically (keeping the
 * `slug(label) === fieldKey` link intact). An empty or colliding label is // i18n-ignore
 * rejected by the store and the row reverts to the previous label.
 */
const SortableFieldItem: React.FC<{
  fieldKey: string;
  pageNumber: number;
  index: number;
  label: string;
  type: FieldType | undefined;
  onRename: (fieldKey: string, newLabel: string) => boolean;
}> = ({ fieldKey, pageNumber, index, label, type, onRename }) => {
  const data: DragMeta = useMemo(
    () => ({ type: "field", fieldKey, pageNumber, index }),
    [fieldKey, pageNumber, index]
  );
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `field-${fieldKey}`,
    data,
  });

  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(label);

  const beginEdit = useCallback(() => {
    setDraft(label);
    setIsEditing(true);
  }, [label]);

  const commitEdit = useCallback(() => {
    setIsEditing(false);
    const trimmed = draft.trim();
    // No change, or a no-op edit: don't touch the store.
    if (trimmed.length === 0 || trimmed === label) return;
    onRename(fieldKey, trimmed);
  }, [draft, label, fieldKey, onRename]);

  const cancelEdit = useCallback(() => {
    setIsEditing(false);
    setDraft(label);
  }, [label]);

  return (
    <Box
      ref={setNodeRef}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        p: 1,
        mb: 0.5,
        borderRadius: 1,
        border: 1,
        borderColor: "divider",
        bgcolor: "background.paper",
        opacity: isDragging ? 0.4 : 1,
        transform: CSS.Transform.toString(transform),
        transition,
      }}
    >
      <IconButton
        size="small"
        aria-label={`Reorder field ${label || fieldKey}`}
        {...attributes}
        {...listeners}
        sx={{ cursor: "grab", touchAction: "none" }}
      >
        <DragIcon fontSize="small" />
      </IconButton>
      {isEditing ? (
        <TextField
          autoFocus
          size="small"
          variant="standard"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commitEdit();
            } else if (e.key === "Escape") {
              e.preventDefault();
              cancelEdit();
            }
          }}
          aria-label={`Field label for ${label || fieldKey}`}
          sx={{ flex: 1, minWidth: 0 }}
        />
      ) : (
        <Typography
          variant="body2"
          sx={{ flex: 1, minWidth: 0, cursor: "text" }}
          noWrap
          onDoubleClick={beginEdit}
          // i18n-ignore
          title="Double-click to rename"
        >
          {label || fieldKey}
        </Typography>
      )}
      {type && <Chip label={type} size="small" variant="outlined" />}
      {!isEditing && (
        <Tooltip
          // i18n-ignore
          title="Rename field"
        >
          <IconButton
            size="small"
            aria-label={`Rename field ${label || fieldKey}`}
            onClick={beginEdit}
          >
            <EditIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
};

/**
 * A non-`metadata-field` built-in element (destination selector, path
 * questions, uploader) rendered as a read-only chip. These are placed via
 * dedicated store actions (e.g. `setUploaderPage`), not by dragging from the
 * palette, so they are not sortable here.
 */
const ELEMENT_LABELS: Record<Exclude<PortalPageElement["kind"], "metadata-field">, string> = {
  "destination-selector": "Destination selector",
  "path-browser": "Path browser",
  "path-builder": "Path builder",
  uploader: "Uploader",
};

/**
 * A sortable page card. The card itself is the sortable node (for page
 * reordering); its inner body is a separate droppable region that accepts
 * palette drops and cross-page field moves. The drag handle is the header
 * {@link DragIcon} so dragging never starts from inside the field list.
 */
const SortablePage: React.FC<{
  page: PortalPage;
  index: number;
  fields: readonly PortalMetadataField[];
  onRemove: (pageNumber: number) => void;
  onSetUploader: (pageNumber: number) => void;
  onRenameField: (fieldKey: string, newLabel: string) => boolean;
  onRenamePage: (pageNumber: number, newTitle: string) => void;
}> = ({ page, index, fields, onRemove, onSetUploader, onRenameField, onRenamePage }) => {
  const pageData: DragMeta = useMemo(
    () => ({ type: "page", pageNumber: page.pageNumber, index }),
    [page.pageNumber, index]
  );
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `page-${page.pageNumber}`,
    data: pageData,
  });

  // Defensive: a page may arrive without an `elements` array (older saved
  // portals / partial backend payloads). Normalize to [] so the length/map/
  // filter reads below never throw "Cannot read properties of undefined".
  const elements = page.elements ?? [];

  // Droppable container for this page's field list. Dropping anywhere in the
  // body that is NOT over a specific field resolves to "append to the end" of
  // the page's `elements` array. Field-specific positions come from the
  // sortable field rows themselves (their `over` target carries the index).
  const dropData: DropMeta = useMemo(
    () => ({ type: "page-container", pageNumber: page.pageNumber, index: elements.length }),
    [page.pageNumber, elements.length]
  );
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `page-container-${page.pageNumber}`,
    data: dropData,
  });

  // Resolve a field's display label/type from its slugified key.
  const fieldByKey = useMemo(() => {
    const map = new Map<string, PortalMetadataField>();
    for (const f of fields) map.set(slug(f.label), f);
    return map;
  }, [fields]);

  // Field elements paired with their index in the *full* `elements` array,
  // which is the index the store's field actions expect.
  const fieldElements = useMemo(
    () =>
      elements
        .map((el, elementIndex) => ({ el, elementIndex }))
        .filter(
          (
            entry
          ): entry is {
            el: Extract<PortalPageElement, { kind: "metadata-field" }>;
            elementIndex: number;
          } => entry.el.kind === "metadata-field"
        ),
    [elements]
  );
  const fieldItemIds = useMemo(
    () => fieldElements.map(({ el }) => `field-${el.fieldKey}`),
    [fieldElements]
  );

  const builtInElements = elements.filter(
    (el): el is Exclude<PortalPageElement, { kind: "metadata-field" }> =>
      el.kind !== "metadata-field"
  );
  const hostsUploader = builtInElements.some((el) => el.kind === "uploader");

  // Inline page-title editing. Click the title (or the edit button) to swap
  // the read-only label for a text field; commit on blur/Enter, cancel on Esc.
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(page.title ?? "");

  const beginTitleEdit = useCallback(() => {
    setTitleDraft(page.title ?? "");
    setIsEditingTitle(true);
  }, [page.title]);

  const commitTitleEdit = useCallback(() => {
    setIsEditingTitle(false);
    const trimmed = titleDraft.trim();
    if (trimmed === (page.title ?? "")) return;
    onRenamePage(page.pageNumber, trimmed);
  }, [titleDraft, page.title, page.pageNumber, onRenamePage]);

  const cancelTitleEdit = useCallback(() => {
    setIsEditingTitle(false);
    setTitleDraft(page.title ?? "");
  }, [page.title]);

  return (
    <Paper
      ref={setNodeRef}
      variant="outlined"
      sx={{
        p: 1.5,
        opacity: isDragging ? 0.5 : 1,
        transform: CSS.Transform.toString(transform),
        transition,
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <IconButton
          size="small"
          aria-label={`Reorder page ${page.pageNumber}`}
          {...attributes}
          {...listeners}
          sx={{ cursor: "grab", touchAction: "none" }}
        >
          <DragIcon fontSize="small" />
        </IconButton>
        {isEditingTitle ? (
          <TextField
            autoFocus
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
            aria-label={`Title for page ${page.pageNumber}`}
            sx={{ flex: 1, minWidth: 0 }}
          />
        ) : (
          <Typography
            variant="subtitle2"
            sx={{ flex: 1, minWidth: 0, cursor: "text" }}
            noWrap
            onDoubleClick={beginTitleEdit}
            // i18n-ignore
            title="Double-click to rename"
          >
            {page.pageNumber}. {page.title || "Untitled page"}
          </Typography>
        )}
        {!isEditingTitle && (
          <Tooltip
            // i18n-ignore
            title="Rename page"
          >
            <IconButton
              size="small"
              aria-label={`Rename page ${page.pageNumber}`}
              onClick={beginTitleEdit}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={hostsUploader ? "This page hosts the uploader" : "Place the uploader here"}>
          <span>
            <IconButton
              size="small"
              color={hostsUploader ? "primary" : "default"}
              aria-label={`Set uploader on page ${page.pageNumber}`}
              aria-pressed={hostsUploader}
              onClick={() => onSetUploader(page.pageNumber)}
            >
              <CloudUploadIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip
          // i18n-ignore
          title="Remove page"
        >
          <span>
            <IconButton
              size="small"
              aria-label={`Remove page ${page.pageNumber}`}
              onClick={() => onRemove(page.pageNumber)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>

      <Box
        ref={setDropRef}
        sx={{
          minHeight: 56,
          p: 1,
          borderRadius: 1,
          border: 1,
          borderStyle: "dashed",
          borderColor: isOver ? "primary.main" : "divider",
          bgcolor: isOver ? "action.hover" : "transparent",
          transition: "background-color 120ms, border-color 120ms",
        }}
      >
        <SortableContext items={fieldItemIds} strategy={verticalListSortingStrategy}>
          {fieldElements.map(({ el, elementIndex }) => {
            const field = fieldByKey.get(el.fieldKey);
            return (
              <SortableFieldItem
                key={el.fieldKey}
                fieldKey={el.fieldKey}
                pageNumber={page.pageNumber}
                index={elementIndex}
                label={field?.label ?? el.fieldKey}
                type={field?.type}
                onRename={onRenameField}
              />
            );
          })}
        </SortableContext>

        {fieldElements.length === 0 && (
          <Typography variant="caption" color="text.secondary">
            Drag a field type here to add a field to this page.
          </Typography>
        )}

        {builtInElements.length > 0 && (
          <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
            {builtInElements.map((el, i) => (
              <Chip key={`${el.kind}-${i}`} label={ELEMENT_LABELS[el.kind]} size="small" />
            ))}
          </Box>
        )}
      </Box>
    </Paper>
  );
};

/**
 * PagesWorkflowSection
 *
 * The accessible dnd-kit authoring surface for the "Pages & Workflow" editor
 * section (Requirements 8.1–8.3, 8.6, 8.7). It renders:
 *
 *   - a palette of draggable field types (text / email / number / select),
 *   - a vertically-sortable list of pages, and
 *   - a vertically-sortable list of `metadata-field` elements inside each page,
 *     whose body also acts as a drop target for palette items and cross-page
 *     field moves.
 *
 * `DndContext` is configured with the Pointer and Keyboard sensors (the latter
 * using `sortableKeyboardCoordinates`) so every interaction is fully operable
 * by keyboard alone (Requirement 8.2). `onDragEnd` inspects `active`/`over`
 * `data` and routes to the store's page actions:
 *
 *   - palette item → `addFieldToPage(fieldType, pageNumber, index)` // i18n-ignore
 *   - cross-page field move → `assignFieldToPage(fieldKey, pageNumber, index)` // i18n-ignore
 *   - same-page field reorder → `reorderFieldWithinPage(fieldKey, index)` // i18n-ignore
 *   - page reorder → `reorderPages(fromPageNumber, toIndex)` // i18n-ignore
 *
 * A cancelled drag or a release outside a valid target (`!over`, or an
 * incompatible target type) returns without mutating the store, leaving page
 * order, field order, and page assignments unchanged (Requirement 8.6). Custom
 * `announcements` emit live-region status messages that name the affected page
 * or field on start/move/end/cancel (Requirement 8.7).
 *
 * NOTE: This section is not yet wired into the editor sidebar/section order —
 * that happens in task 13.3.
 */
const PagesWorkflowSection: React.FC = () => {
  const pages = usePortalEditorStore(
    (s) => (s.portalData?.pages as PortalPage[] | undefined) ?? (EMPTY_PAGES as PortalPage[])
  );
  const fields = usePortalEditorStore(
    (s) =>
      (s.portalData?.metadataFields as PortalMetadataField[] | undefined) ??
      (EMPTY_FIELDS as PortalMetadataField[])
  );
  const pageErrors = usePortalEditorStore((s) => s.validationErrors.pages);

  const addPage = usePortalEditorStore((s) => s.addPage);
  const removePage = usePortalEditorStore((s) => s.removePage);
  const reorderPages = usePortalEditorStore((s) => s.reorderPages);
  const addFieldToPage = usePortalEditorStore((s) => s.addFieldToPage);
  const assignFieldToPage = usePortalEditorStore((s) => s.assignFieldToPage);
  const reorderFieldWithinPage = usePortalEditorStore((s) => s.reorderFieldWithinPage);
  const renameField = usePortalEditorStore((s) => s.renameField);
  const updatePage = usePortalEditorStore((s) => s.updatePage);
  const setUploaderPage = usePortalEditorStore((s) => s.setUploaderPage);

  // Label for the floating drag overlay; null while nothing is being dragged.
  const [activeLabel, setActiveLabel] = useState<string | null>(null);
  // The active drag source's mode ("page" vs "field"), used by the custom
  // collision detection to ignore droppables irrelevant to the current drag.
  // A ref (not state) so the collision callback always reads the latest value
  // without being recreated on every drag.
  const dragModeRef = useRef<DragMode>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const pageItemIds = useMemo(() => pages.map((p) => `page-${p.pageNumber}`), [pages]);

  /**
   * Mode-aware collision detection. Nesting three droppable layers (sortable
   * pages → each page's field container → sortable field rows) in one
   * `DndContext` makes `closestCenter` resolve `over` to the wrong layer (often
   * the page card), which made field drags silently no-op. Instead we:
   *
   *   1. filter the droppables to only those relevant to the active drag mode
   *      (page reorder → page nodes only; field move → field rows + page
   *      containers only), then
   *   2. prefer `pointerWithin` (most accurate for nested/overlapping targets)
   *      and fall back to `rectIntersection` when the pointer is between rows.
   */
  const collisionDetection: CollisionDetection = useCallback((args) => {
    const mode = dragModeRef.current;
    const filtered =
      mode === "page"
        ? args.droppableContainers.filter((c) => {
            const meta = asDropMeta(c.data.current);
            return meta?.type === "page";
          })
        : args.droppableContainers.filter((c) => {
            const meta = asDropMeta(c.data.current);
            return meta?.type === "field" || meta?.type === "page-container";
          });

    const scoped = { ...args, droppableContainers: filtered };
    const within = pointerWithin(scoped);
    if (within.length > 0) return within;
    return rectIntersection(scoped);
  }, []);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const meta = asDragMeta(event.active.data.current);
    dragModeRef.current = dragModeFor(meta);
    setActiveLabel(describeMeta(meta));
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveLabel(null);
      dragModeRef.current = null;
      const { active, over } = event;
      // Cancelled / released outside any droppable: leave the store untouched
      // (Requirement 8.6).
      if (!over) return;

      const a = asDragMeta(active.data.current);
      const o = asDropMeta(over.data.current);
      if (!a || !o) return;

      if (a.type === "palette-item") {
        // Palette → page: create a new field at the resolved drop position.
        const drop = resolveFieldDrop(o);
        if (drop) {
          addFieldToPage(a.fieldType, drop.pageNumber, drop.index, a.role);
        }
        return;
      }

      if (a.type === "field") {
        const drop = resolveFieldDrop(o);
        if (!drop) return;
        // Dropping a field onto itself is a no-op.
        if (o.type === "field" && o.fieldKey === a.fieldKey) return;
        if (drop.pageNumber !== a.pageNumber) {
          // Cross-page move: reassign the field's page + position.
          assignFieldToPage(a.fieldKey, drop.pageNumber, drop.index);
        } else {
          // Same-page reorder.
          reorderFieldWithinPage(a.fieldKey, drop.index);
        }
        return;
      }

      if (a.type === "page") {
        // Page reorder is only valid when dropped over another page.
        if (o.type === "page") {
          reorderPages(a.pageNumber, o.index);
        }
      }
    },
    [addFieldToPage, assignFieldToPage, reorderFieldWithinPage, reorderPages]
  );

  const handleRenamePage = useCallback(
    (pageNumber: number, newTitle: string) => {
      updatePage(pageNumber, { title: newTitle });
    },
    [updatePage]
  );

  const handleDragCancel = useCallback(() => {
    setActiveLabel(null);
    dragModeRef.current = null;
  }, []);

  // Live-region announcements naming the affected page/field (Requirement 8.7).
  const announcements: Announcements = useMemo(
    () => ({
      onDragStart: ({ active }) => `Picked up ${describeMeta(asDragMeta(active.data.current))}.`,
      onDragOver: ({ active, over }) =>
        over
          ? `${describeMeta(asDragMeta(active.data.current))} is over ${describeMeta(
              asDropMeta(over.data.current)
            )}.`
          : `${describeMeta(asDragMeta(active.data.current))} is no longer over a drop target.`,
      onDragEnd: ({ active, over }) =>
        over
          ? `${describeMeta(asDragMeta(active.data.current))} was dropped onto ${describeMeta(
              asDropMeta(over.data.current)
            )}.`
          : `${describeMeta(asDragMeta(active.data.current))} was dropped. No changes were made.`,
      onDragCancel: ({ active }) =>
        `Dragging ${describeMeta(
          asDragMeta(active.data.current)
        )} was cancelled. No changes were made.`,
    }),
    []
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionDetection}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
      accessibility={{ announcements }}
    >
      <Stack spacing={2}>
        {pageErrors && pageErrors.length > 0 && (
          <Alert severity="error">
            <Stack spacing={0.5}>
              {pageErrors.map((err) => (
                <span key={`${err.field}-${err.message}`}>{err.message}</span>
              ))}
            </Stack>
          </Alert>
        )}

        <Box>
          <Typography variant="subtitle2" gutterBottom>
            Field types
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            Drag a field type onto a page to add a new metadata field.
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {FIELD_TYPES.map(({ type, label }) => (
              <PaletteItem key={type} fieldType={type} label={label} />
            ))}
            {SPECIAL_FIELD_TYPES.map(({ type, role, label }) => (
              <PaletteItem key={role} fieldType={type} role={role} label={label} />
            ))}
          </Box>
        </Box>

        <Divider />

        <Box>
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="subtitle2">Pages</Typography>
            <Button size="small" startIcon={<AddIcon />} onClick={addPage}>
              Add Page
            </Button>
          </Stack>

          {pages.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No pages yet. Add a page to start building the upload flow.
            </Typography>
          ) : (
            <SortableContext items={pageItemIds} strategy={verticalListSortingStrategy}>
              <Stack spacing={1.5}>
                {pages.map((page, index) => (
                  <SortablePage
                    key={page.pageNumber}
                    page={page}
                    index={index}
                    fields={fields}
                    onRemove={removePage}
                    onSetUploader={setUploaderPage}
                    onRenameField={renameField}
                    onRenamePage={handleRenamePage}
                  />
                ))}
              </Stack>
            </SortableContext>
          )}
        </Box>
      </Stack>

      <DragOverlay>
        {activeLabel ? (
          <Chip
            icon={<DragIcon />}
            label={activeLabel}
            color="primary"
            sx={{ cursor: "grabbing" }}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};

export { PagesWorkflowSection };
export default React.memo(PagesWorkflowSection);
