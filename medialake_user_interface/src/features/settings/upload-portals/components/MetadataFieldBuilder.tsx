import React from "react";
import { useTranslation } from "react-i18next";
import {
  Autocomplete,
  Box,
  Chip,
  TextField,
  Select,
  MenuItem,
  Switch,
  IconButton,
  Button,
  FormControlLabel,
  Typography,
} from "@mui/material";
import {
  DragIndicator as DragIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
} from "@mui/icons-material";
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { PortalMetadataField } from "@/api/types/api.types";

/** A collection the admin can add to a collection-picker field's allow-list. */
export interface CollectionOption {
  id: string;
  name: string;
}

interface Props {
  fields: PortalMetadataField[];
  onChange: (fields: PortalMetadataField[]) => void;
  fieldErrors?: string[];
  /**
   * Optional atomic-rename callback. When provided, label edits are committed
   * through this (on blur / Enter) instead of the plain `onChange` path so the
   * field's `label` AND every referencing page element's `fieldKey` stay in
   * sync (the `slug(label) === fieldKey` invariant). Receives the field's
   * CURRENT key (`slug(field.label)` before the edit) and the new label.
   *
   * Without it the label edit falls back to `onChange`, which only changes the
   * label text — safe only for portals that have no page elements referencing
   * the field by key (e.g. the legacy flat-form usage).
   */
  onRenameField?: (oldFieldKey: string, newLabel: string) => void;
  /**
   * Collections the admin may add to a `collection-picker` field's allow-list.
   * Passed in by the parent (which owns the data fetch) so this component stays
   * decoupled and unit-testable without a query client. Defaults to empty.
   */
  availableCollections?: CollectionOption[];
}

/**
 * Slugify a label into the `fieldKey` a `metadata-field` page element uses to
 * reference its field. Mirrors the helper in `usePortalEditorStore.ts` and
 * `shared/portalSurveyModel.ts`.
 */
const slug = (label: string): string =>
  label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

/**
 * Metadata field types that are choice-based and therefore expose an editable
 * list of `options` (a fixed pick-list shown to the end user). Mirrors the
 * choice-type set in `shared/portalSurveyModel.ts`. `tagbox` is intentionally
 * excluded — it is a free-entry multi-value field, not a fixed pick-list.
 */
const CHOICE_FIELD_TYPES: ReadonlySet<PortalMetadataField["type"]> = new Set([
  "select",
  "radiogroup",
  "checkbox",
]);

/**
 * A single sortable metadata-field row. The drag handle is the {@link DragIcon}
 * `IconButton` so that focusing/activating it starts the drag with either the
 * pointer or the keyboard (the rest of the row stays interactive). Reordering is
 * driven by dnd-kit's {@link useSortable}, replacing the previous native HTML5
 * `draggable`/`onDragStart`/`onDrop` handlers (Requirement 8.5).
 */
const SortableFieldRow: React.FC<{
  id: string;
  index: number;
  field: PortalMetadataField;
  error?: string;
  onUpdate: (index: number, updates: Partial<PortalMetadataField>) => void;
  onRemove: (index: number) => void;
  onRenameLabel?: (index: number, newLabel: string) => void;
  availableCollections?: CollectionOption[];
}> = ({
  id,
  index,
  field,
  error,
  onUpdate,
  onRemove,
  onRenameLabel,
  availableCollections = [],
}) => {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  });

  const isCollectionPicker = field.role === "collection-picker";
  const isChoiceField = !isCollectionPicker && CHOICE_FIELD_TYPES.has(field.type);
  const options = field.options ?? [];
  const allowedCollections = field.roleConfig?.allowedCollections ?? [];

  // When an atomic-rename handler is supplied, the label is edited through a
  // local draft committed on blur/Enter so the field's key and every
  // referencing page element stay in sync. Otherwise the label edits inline
  // through `onUpdate` (legacy flat-form behavior).
  const [labelDraft, setLabelDraft] = React.useState(field.label);
  React.useEffect(() => {
    setLabelDraft(field.label);
  }, [field.label]);

  const commitLabel = () => {
    if (!onRenameLabel) return;
    const trimmed = labelDraft.trim();
    if (trimmed.length === 0 || trimmed === field.label) {
      setLabelDraft(field.label);
      return;
    }
    onRenameLabel(index, trimmed);
  };

  const updateOption = (optionIndex: number, value: string) => {
    const next = [...options];
    next[optionIndex] = value;
    onUpdate(index, { options: next });
  };

  const addOption = () => {
    onUpdate(index, { options: [...options, ""] });
  };

  const removeOption = (optionIndex: number) => {
    onUpdate(index, { options: options.filter((_, i) => i !== optionIndex) });
  };

  return (
    <Box
      ref={setNodeRef}
      sx={{
        mb: 1.5,
        pb: 1.5,
        borderBottom: 1,
        borderColor: "divider",
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.4 : 1,
      }}
    >
      {/* Row 1: drag handle + the field label (full width). */}
      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
        <IconButton
          size="small"
          aria-label={`Reorder field ${field.label || index + 1}`}
          {...attributes}
          {...listeners}
          sx={{ cursor: "grab", touchAction: "none", color: "text.secondary", mt: 0.5 }}
        >
          <DragIcon fontSize="small" />
        </IconButton>
        <TextField
          label="Field label"
          size="small"
          value={onRenameLabel ? labelDraft : field.label}
          onChange={(e) =>
            onRenameLabel
              ? setLabelDraft(e.target.value)
              : onUpdate(index, { label: e.target.value })
          }
          onBlur={onRenameLabel ? commitLabel : undefined}
          onKeyDown={
            onRenameLabel
              ? (e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commitLabel();
                  } else if (e.key === "Escape") {
                    e.preventDefault();
                    setLabelDraft(field.label);
                  }
                }
              : undefined
          }
          sx={{ flex: 1 }}
          error={!!error}
          helperText={error}
        />
      </Box>

      {/* Row 2: field type + required toggle + delete, indented to align
          under the label (past the drag-handle column). */}
      <Box
        sx={{
          display: "flex",
          gap: 1,
          alignItems: "center",
          ml: 5,
          mt: 1,
        }}
      >
        {isCollectionPicker ? (
          <Box sx={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 1 }}>
            <Chip label="Collection Picker" size="small" color="primary" variant="outlined" />
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={field.roleConfig?.multiple ?? true}
                  onChange={(_, checked) =>
                    onUpdate(index, {
                      roleConfig: { ...field.roleConfig, multiple: checked },
                    })
                  }
                />
              }
              label="Allow multiple"
            />
          </Box>
        ) : (
          <Select
            size="small"
            value={field.type}
            onChange={(e) =>
              onUpdate(index, { type: e.target.value as PortalMetadataField["type"] })
            }
            SelectDisplayProps={{
              "aria-label": `Field type for ${field.label || `field ${index + 1}`}`,
            }}
            sx={{ flex: 1, minWidth: 0 }}
          >
            <MenuItem value="text">Text</MenuItem>
            <MenuItem value="number">Number</MenuItem>
            <MenuItem value="select">Dropdown</MenuItem>
            <MenuItem value="radiogroup">{t("uploadPortals.fieldTypes.radioGroup")}</MenuItem>
            <MenuItem value="checkbox">Checkboxes</MenuItem>
            <MenuItem value="tagbox">Tags</MenuItem>
            <MenuItem value="boolean">{t("uploadPortals.fieldTypes.yesNo")}</MenuItem>
          </Select>
        )}
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={field.required}
              onChange={(_, checked) => onUpdate(index, { required: checked })}
            />
          }
          label="Required"
        />
        <IconButton
          size="small"
          aria-label={`Remove field ${field.label || index + 1}`}
          onClick={() => onRemove(index)}
        >
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Box>

      {isCollectionPicker && (
        <Box sx={{ ml: 5, mt: 1, mb: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            Collections the uploader can choose from
          </Typography>
          <Autocomplete
            multiple
            size="small"
            options={availableCollections}
            getOptionLabel={(o) => o.name}
            isOptionEqualToValue={(o, v) => o.id === v.id}
            value={allowedCollections}
            onChange={(_, next) =>
              onUpdate(index, {
                roleConfig: {
                  ...field.roleConfig,
                  allowedCollections: next.map((c) => ({ id: c.id, name: c.name })),
                },
              })
            }
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder={
                  availableCollections.length === 0 ? "Loading collections…" : "Select collections"
                }
                aria-label={`Allowed collections for ${field.label || `field ${index + 1}`}`}
              />
            )}
          />
          <Typography variant="caption" color="text.secondary">
            Uploaders pick from this list; the server only honors collections in it. Leave empty to
            disable selection.
          </Typography>
        </Box>
      )}

      {isChoiceField && (
        <Box
          sx={{
            // Indent the options editor under the field row, past the drag handle.
            ml: 5,
            mt: 1,
            mb: 1,
            display: "flex",
            flexDirection: "column",
            gap: 0.5,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            Choices
          </Typography>
          {options.map((option, optionIndex) => (
            <Box key={optionIndex} sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <TextField
                size="small"
                value={option}
                placeholder={`Option ${optionIndex + 1}`}
                onChange={(e) => updateOption(optionIndex, e.target.value)}
                aria-label={`Option ${optionIndex + 1} for ${field.label || `field ${index + 1}`}`}
                sx={{ flex: 1 }}
              />
              <IconButton
                size="small"
                aria-label={`Remove option ${optionIndex + 1}`}
                onClick={() => removeOption(optionIndex)}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
          ))}
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={addOption}
            sx={{ alignSelf: "flex-start" }}
          >
            Add Choice
          </Button>
        </Box>
      )}
    </Box>
  );
};

/**
 * MetadataFieldBuilder
 *
 * Edits the ordered list of {@link PortalMetadataField}s for a portal page.
 * Reordering uses dnd-kit's accessible sortable interactions — `DndContext`
 * with the Pointer and Keyboard sensors (the latter via
 * `sortableKeyboardCoordinates`) wrapping a `SortableContext` with the vertical
 * list strategy — so fields can be reordered by keyboard alone (Requirement
 * 8.5). On drag end the rows are reordered with `arrayMove` and `order` is reset
 * to the array index, preserving the previous behavior.
 *
 * Stable sortable identity: `PortalMetadataField` has no id, and labels may be
 * empty or duplicated, so neither the array index nor the label is a
 * reorder-safe key. Instead an internal `ids` list (a `useRef` of generated
 * strings from an incrementing counter) is kept positionally aligned with
 * `fields`: `ids[i]` is the identity of `fields[i]`. add/remove/reorder mutate
 * both arrays identically (append, splice-at-index, and `arrayMove`
 * respectively) so identity travels with each field across a reorder. A
 * render-time length reconciliation regenerates/truncates ids only when the
 * parent replaces `fields` wholesale (e.g. loading a saved portal).
 *
 * The public Props contract is unchanged: `{ fields, onChange, fieldErrors }`.
 */
const MetadataFieldBuilder: React.FC<Props> = ({
  fields,
  onChange,
  fieldErrors,
  onRenameField,
  availableCollections,
}) => {
  const idsRef = React.useRef<string[]>([]);
  const counterRef = React.useRef(0);

  // Keep `ids` length-aligned with `fields`. add/remove/reorder below keep the
  // arrays aligned explicitly; this only handles a wholesale replacement of
  // `fields` by the parent (different length than our tracked ids).
  if (idsRef.current.length < fields.length) {
    const next = [...idsRef.current];
    while (next.length < fields.length) {
      next.push(`mdf-${counterRef.current++}`);
    }
    idsRef.current = next;
  } else if (idsRef.current.length > fields.length) {
    idsRef.current = idsRef.current.slice(0, fields.length);
  }
  const ids = idsRef.current;

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const addField = () => {
    idsRef.current = [...idsRef.current, `mdf-${counterRef.current++}`];
    onChange([...fields, { label: "", type: "text", required: false, order: fields.length }]);
  };

  const updateField = (i: number, updates: Partial<PortalMetadataField>) => {
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...updates } : f)));
  };

  const removeField = (i: number) => {
    idsRef.current = idsRef.current.filter((_, idx) => idx !== i);
    onChange(fields.filter((_, idx) => idx !== i).map((f, idx) => ({ ...f, order: idx })));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    // Cancelled or released outside a target / onto itself: no change.
    if (!over || active.id === over.id) return;

    const oldIndex = ids.indexOf(String(active.id));
    const newIndex = ids.indexOf(String(over.id));
    if (oldIndex === -1 || newIndex === -1) return;

    // Reorder ids and fields identically so identity stays aligned, then reset
    // `order` to the new array index (preserving the previous behavior).
    idsRef.current = arrayMove(idsRef.current, oldIndex, newIndex);
    onChange(arrayMove(fields, oldIndex, newIndex).map((f, idx) => ({ ...f, order: idx })));
  };

  return (
    <Box>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {fields.map((field, i) => (
            <SortableFieldRow
              key={ids[i]}
              id={ids[i]}
              index={i}
              field={field}
              error={fieldErrors?.[i]}
              onUpdate={updateField}
              onRemove={removeField}
              onRenameLabel={
                onRenameField
                  ? (idx, newLabel) => onRenameField(slug(fields[idx].label), newLabel)
                  : undefined
              }
              availableCollections={availableCollections}
            />
          ))}
        </SortableContext>
      </DndContext>
      <Button size="small" startIcon={<AddIcon />} onClick={addField}>
        Add Field
      </Button>
    </Box>
  );
};

export default MetadataFieldBuilder;
