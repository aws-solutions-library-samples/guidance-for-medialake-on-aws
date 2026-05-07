import React, { useCallback, useMemo } from "react";
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Add as AddIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Delete as DeleteIcon,
  DragIndicator as DragIndicatorIcon,
} from "@mui/icons-material";
import type {
  PathSegmentType,
  PathSegmentRuleExtended,
} from "@/features/portal/types/portal.types";

let segmentIdCounter = 0;
/** Generate a stable unique id for a new segment. */
function generateSegmentId(): string {
  segmentIdCounter += 1;
  return `seg_${Date.now()}_${segmentIdCounter}`;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

/**
 * Auto-generate a regex pattern from a user-friendly segment type.
 * The backend `PathSegmentRule.regex` field is populated with this value.
 */
export function generateRegexFromType(type: PathSegmentType, listValues?: string[]): string {
  switch (type) {
    case "text":
      return "^.+$";
    case "alphanumeric":
      return "^[a-zA-Z0-9]+$";
    case "numbers":
      return "^\\d+$";
    case "date":
      return "^\\d{4}-\\d{2}-\\d{2}$";
    case "list":
      return listValues?.length
        ? `^(${listValues.map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})$`
        : "^.+$";
    case "pattern":
      return ""; // admin provides their own
    default:
      return "^.+$";
  }
}

/**
 * Return an example value for the live path preview based on segment type.
 */
export function getExampleValue(type: PathSegmentType, listValues?: string[]): string {
  switch (type) {
    case "text":
      return "example";
    case "alphanumeric":
      return "ABC123";
    case "numbers":
      return "42";
    case "date":
      return "2024-01-15";
    case "list":
      return listValues?.[0] ?? "option1";
    case "pattern":
      return "value";
    default:
      return "value";
  }
}

/** Human-readable labels for the type dropdown. */
const TYPE_OPTIONS: { value: PathSegmentType; label: string }[] = [
  { value: "text", label: "Free text" },
  { value: "alphanumeric", label: "Alphanumeric" },
  { value: "numbers", label: "Numbers only" },
  { value: "date", label: "Date (YYYY-MM-DD)" },
  { value: "list", label: "Choose from list" },
  { value: "pattern", label: "Custom pattern" },
];

const SEPARATOR_OPTIONS = ["/", "-", "_", "."] as const;

/* ------------------------------------------------------------------ */
/*  Props                                                             */
/* ------------------------------------------------------------------ */

interface PathSegmentBuilderProps {
  segments: PathSegmentRuleExtended[];
  onChange: (segments: PathSegmentRuleExtended[]) => void;
  separator?: string;
  onSeparatorChange?: (sep: string) => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

const PathSegmentBuilder: React.FC<PathSegmentBuilderProps> = ({
  segments,
  onChange,
  separator = "/",
  onSeparatorChange,
}) => {
  /* ---- segment CRUD ---- */

  const addSegment = useCallback(() => {
    const newSeg: PathSegmentRuleExtended = {
      id: generateSegmentId(),
      label: "",
      position: segments.length,
      regex: generateRegexFromType("text"),
      segmentType: "text",
      required: true,
    };
    onChange([...segments, newSeg]);
  }, [segments, onChange]);

  const updateSegment = useCallback(
    (index: number, updates: Partial<PathSegmentRuleExtended>) => {
      onChange(
        segments.map((seg, i) => {
          if (i !== index) return seg;
          const updated = { ...seg, ...updates };

          // Auto-regenerate regex when type or list values change
          if ("segmentType" in updates || "listValues" in updates) {
            const type = updated.segmentType ?? "text";
            if (type !== "pattern") {
              updated.regex = generateRegexFromType(type, updated.listValues);
            }
          }

          return updated;
        })
      );
    },
    [segments, onChange]
  );

  const removeSegment = useCallback(
    (index: number) => {
      const updated = segments
        .filter((_, i) => i !== index)
        .map((seg, i) => ({ ...seg, position: i }));
      onChange(updated);
    },
    [segments, onChange]
  );

  const moveSegment = useCallback(
    (index: number, direction: "up" | "down") => {
      const target = direction === "up" ? index - 1 : index + 1;
      if (target < 0 || target >= segments.length) return;
      const copy = [...segments];
      [copy[index], copy[target]] = [copy[target], copy[index]];
      onChange(copy.map((seg, i) => ({ ...seg, position: i })));
    },
    [segments, onChange]
  );

  /* ---- live preview ---- */

  const previewPath = useMemo(() => {
    if (segments.length === 0) return "";
    return segments
      .map((seg) => {
        const type = seg.segmentType ?? "text";
        const example = getExampleValue(type, seg.listValues);
        return seg.label ? `${example}` : example;
      })
      .join(separator);
  }, [segments, separator]);

  const previewLabels = useMemo(() => {
    if (segments.length === 0) return "";
    return segments.map((seg) => (seg.label ? `{${seg.label}}` : "{...}")).join(separator);
  }, [segments, separator]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Segment cards */}
      {segments.map((seg, index) => (
        <Paper
          key={seg.id}
          variant="outlined"
          sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.5 }}
        >
          {/* Top row: drag handle, label, type, actions */}
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <DragIndicatorIcon
                fontSize="small"
                sx={{ color: "text.secondary", cursor: "default" }}
              />

              <TextField
                label="Label"
                size="small"
                value={seg.label}
                onChange={(e) => updateSegment(index, { label: e.target.value })}
                sx={{ flex: 1 }}
                placeholder="e.g. Department" // i18n-ignore
              />

              {/* Move up / down / delete */}
              {/* i18n-ignore */}
              <Tooltip title="Move up">
                <span>
                  <IconButton
                    size="small"
                    disabled={index === 0}
                    onClick={() => moveSegment(index, "up")}
                    aria-label="Move segment up"
                  >
                    <ArrowUpIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              {/* i18n-ignore */}
              <Tooltip title="Move down">
                <span>
                  <IconButton
                    size="small"
                    disabled={index === segments.length - 1}
                    onClick={() => moveSegment(index, "down")}
                    aria-label="Move segment down"
                  >
                    <ArrowDownIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              {/* i18n-ignore */}
              <Tooltip title="Remove segment">
                <IconButton
                  size="small"
                  onClick={() => removeSegment(index)}
                  aria-label="Remove segment"
                  color="error"
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>

            <Select
              size="small"
              value={seg.segmentType ?? "text"}
              onChange={(e) =>
                updateSegment(index, {
                  segmentType: e.target.value as PathSegmentType,
                })
              }
              fullWidth
            >
              {TYPE_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </Box>

          {/* Type-specific options */}
          {seg.segmentType === "list" && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <TextField
                label="Allowed values (comma-separated)"
                size="small"
                fullWidth
                value={(seg.listValues ?? []).join(", ")}
                onChange={(e) => {
                  const vals = e.target.value
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean);
                  updateSegment(index, { listValues: vals });
                }}
                placeholder="e.g. Marketing, Engineering, Sales" // i18n-ignore
                helperText="Enter comma-separated values" // i18n-ignore
              />
              {(seg.listValues ?? []).length > 0 && (
                <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
                  {seg.listValues!.map((val, vi) => (
                    <Chip key={vi} label={val} size="small" variant="outlined" />
                  ))}
                </Box>
              )}
            </Box>
          )}

          {seg.segmentType === "pattern" && (
            <TextField
              label="Regular expression pattern"
              size="small"
              fullWidth
              value={seg.regex}
              onChange={(e) => updateSegment(index, { regex: e.target.value })}
              helperText="Regular expression pattern" // i18n-ignore
              placeholder="e.g. ^[A-Z]{3}-\\d{3}$" // i18n-ignore
            />
          )}

          {/* Required switch */}
          <FormControlLabel
            control={
              <Switch
                checked={seg.required !== false}
                onChange={(e) => updateSegment(index, { required: e.target.checked })}
                size="small"
              />
            }
            label="Required"
            sx={{ ml: 0 }}
          />
        </Paper>
      ))}

      {/* Add segment button */}
      <Button
        size="small"
        startIcon={<AddIcon />}
        onClick={addSegment}
        sx={{ alignSelf: "flex-start" }}
      >
        Add segment
      </Button>

      {/* Separator selector */}
      {onSeparatorChange && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Typography variant="body2" color="text.secondary">
            Separator:
          </Typography>
          <ToggleButtonGroup
            value={separator}
            exclusive
            size="small"
            onChange={(_, val) => {
              if (val !== null) onSeparatorChange(val);
            }}
            aria-label="Path separator"
          >
            {SEPARATOR_OPTIONS.map((sep) => (
              <ToggleButton key={sep} value={sep} aria-label={`Separator ${sep}`}>
                <Typography variant="body2" sx={{ fontFamily: "monospace", px: 0.5 }}>
                  {sep}
                </Typography>
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
      )}

      {/* Live path preview */}
      {segments.length > 0 && (
        <Paper
          variant="outlined"
          sx={{
            p: 1.5,
            bgcolor: "action.hover",
            borderStyle: "dashed",
          }}
        >
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Path preview
          </Typography>
          <Typography variant="body2" sx={{ fontFamily: "monospace", wordBreak: "break-all" }}>
            {previewLabels}
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontFamily: "monospace", wordBreak: "break-all", mt: 0.5 }}
          >
            Example: {previewPath}
          </Typography>
        </Paper>
      )}
    </Box>
  );
};

export default PathSegmentBuilder;
