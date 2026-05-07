import React, { useState } from "react";
import {
  Box,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Typography,
} from "@mui/material";
import { PathBrowser } from "@/features/upload/components/PathBrowser";
import { useGetConnectors } from "@/api/hooks/useConnectors";
import type { PortalDestination, PortalPathSegment } from "@/api/types/api.types";
import PathSegmentBuilder from "./PathSegmentBuilder";
import type { PathSegmentRuleExtended } from "@/features/portal/types/portal.types";

interface Props {
  destination?: PortalDestination;
  structuredPathMode: boolean;
  onSave: (dest: PortalDestination) => void;
  onCancel: () => void;
}

/**
 * Convert API path segments to extended segments for the builder.
 * Existing segments without a segmentType default to "pattern" so the
 * raw regex is preserved and editable.
 */
function toExtendedSegments(segments: PortalPathSegment[] | undefined): PathSegmentRuleExtended[] {
  if (!segments) return [];
  return segments.map((seg, i) => ({
    ...seg,
    id: `seg_init_${i}_${Date.now()}`,
    segmentType: (seg.segmentType as PathSegmentRuleExtended["segmentType"]) ?? "pattern",
    listValues: seg.listValues,
    patternDescription: seg.patternDescription,
  }));
}

/**
 * Convert extended segments back to the API shape for persistence.
 */
function toApiSegments(segments: PathSegmentRuleExtended[]): PortalPathSegment[] {
  return segments.map((seg) => ({
    label: seg.label,
    position: seg.position,
    regex: seg.regex,
    segmentType: seg.segmentType,
    listValues: seg.listValues,
    patternDescription: seg.patternDescription,
  }));
}

const DestinationForm: React.FC<Props> = ({
  destination,
  structuredPathMode,
  onSave,
  onCancel,
}) => {
  const { data: connectorsResponse } = useGetConnectors();
  const connectors = connectorsResponse?.data?.connectors ?? [];

  const [friendlyName, setFriendlyName] = useState(destination?.friendlyName ?? "");
  const [connectorId, setConnectorId] = useState(destination?.connectorId ?? "");
  // Root path: empty string "" is valid and means the bucket root ("/").
  // We track whether the user has explicitly selected a path (including root)
  // vs never having opened the browser at all.
  const [rootPath, setRootPath] = useState(destination?.rootPath ?? "");
  const [rootPathSelected, setRootPathSelected] = useState(destination?.rootPath !== undefined);
  const [allowBrowsing, setAllowBrowsing] = useState(destination?.allowBrowsing ?? false);
  const [allowFolderCreation, setAllowFolderCreation] = useState(
    destination?.allowFolderCreation ?? false
  );
  const [pathSegments, setPathSegments] = useState<PathSegmentRuleExtended[]>(
    toExtendedSegments(destination?.pathSegments)
  );
  const [pathSeparator, setPathSeparator] = useState(destination?.pathSeparator ?? "/");
  const [pathBrowserOpen, setPathBrowserOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleSave = () => {
    const newErrors: Record<string, string> = {};
    if (!friendlyName.trim()) newErrors.friendlyName = "Friendly name is required";
    if (!connectorId) newErrors.connectorId = "Connector is required";
    // Root path "" (empty string) is valid — it means the bucket root.
    // Only error if the user never selected a path at all.
    if (!rootPathSelected)
      newErrors.rootPath =
        "Root path is required. Use Browse to select a folder (or the bucket root).";
    if (structuredPathMode) {
      pathSegments.forEach((seg, i) => {
        if (!seg.label.trim()) newErrors[`segment_${i}_label`] = "Label is required";
        if (!seg.regex.trim() && seg.segmentType === "pattern")
          newErrors[`segment_${i}_regex`] = "Regex is required";
      });
    }
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setErrors({});
    onSave({
      destinationId: destination?.destinationId ?? crypto.randomUUID(),
      friendlyName,
      connectorId,
      rootPath,
      allowBrowsing,
      allowFolderCreation,
      order: destination?.order ?? 0,
      ...(structuredPathMode ? { pathSegments: toApiSegments(pathSegments), pathSeparator } : {}),
    });
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <TextField
        label="Friendly Name"
        required
        value={friendlyName}
        onChange={(e) => {
          setFriendlyName(e.target.value);
          setErrors((prev) => {
            const { friendlyName: _, ...rest } = prev;
            return rest;
          });
        }}
        error={!!errors.friendlyName}
        helperText={errors.friendlyName}
        fullWidth
        size="small"
      />

      <FormControl fullWidth size="small" error={!!errors.connectorId}>
        <InputLabel>Connector</InputLabel>
        <Select
          value={connectorId}
          label="Connector"
          onChange={(e) => {
            setConnectorId(e.target.value);
            setErrors((prev) => {
              const { connectorId: _, ...rest } = prev;
              return rest;
            });
          }}
        >
          {connectors.map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.name}
            </MenuItem>
          ))}
        </Select>
        {errors.connectorId && (
          <Typography variant="caption" color="error">
            {errors.connectorId}
          </Typography>
        )}
      </FormControl>

      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <TextField
          label="Root Path"
          value={rootPath || (rootPathSelected ? "/" : "")}
          size="small"
          fullWidth
          slotProps={{ input: { readOnly: true } }}
          error={!!errors.rootPath}
          helperText={
            errors.rootPath ?? (rootPathSelected && !rootPath ? "Bucket root selected" : undefined)
          }
        />
        <Button
          variant="outlined"
          size="small"
          disabled={!connectorId}
          onClick={() => setPathBrowserOpen(true)}
        >
          Browse
        </Button>
      </Box>

      <Box sx={{ display: "flex", gap: 2 }}>
        <FormControlLabel
          control={<Switch checked={allowBrowsing} onChange={(_, v) => setAllowBrowsing(v)} />}
          label="Allow Browsing"
        />
        <FormControlLabel
          control={
            <Switch checked={allowFolderCreation} onChange={(_, v) => setAllowFolderCreation(v)} />
          }
          label="Allow Folder Creation"
        />
      </Box>

      {structuredPathMode && (
        <Box>
          <Typography variant="subtitle2" gutterBottom>
            Path Segments
          </Typography>
          <PathSegmentBuilder
            segments={pathSegments}
            onChange={setPathSegments}
            separator={pathSeparator}
            onSeparatorChange={setPathSeparator}
          />
        </Box>
      )}

      <Box sx={{ display: "flex", gap: 1, justifyContent: "flex-end" }}>
        <Button onClick={onCancel}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!friendlyName || !connectorId || !rootPathSelected}
        >
          {destination ? "Update" : "Add"} Destination
        </Button>
      </Box>

      {connectorId && (
        <PathBrowser
          open={pathBrowserOpen}
          onClose={() => setPathBrowserOpen(false)}
          connectorId={connectorId}
          onPathSelect={(path) => {
            setRootPath(path);
            setRootPathSelected(true);
            setErrors((prev) => {
              const { rootPath: _, ...rest } = prev;
              return rest;
            });
            setPathBrowserOpen(false);
          }}
          initialPath={rootPath}
        />
      )}
    </Box>
  );
};

export default DestinationForm;
