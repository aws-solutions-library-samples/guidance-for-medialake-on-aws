import React, { useEffect, useMemo, useRef, useState } from "react";
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
import type { PortalDestination, PortalPage, PortalPathSegment } from "@/api/types/api.types";
import PathSegmentBuilder from "./PathSegmentBuilder";
import type { PathSegmentRuleExtended } from "@/features/portal/types/portal.types";
import { usePortalEditorStore } from "../stores/usePortalEditorStore";

/**
 * Resolve the page number a new destination should reference.
 *
 * The backend rejects a destination whose `pageNumber` does not point at a
 * real page (e.g. "destination references unknown page None"). To guarantee a
 * valid reference before the payload ever reaches the server, we default to
 * the page hosting the uploader element, falling back to the first page, and
 * finally to page 1 (the create-mode default single page).
 */
const resolveUploaderPageNumber = (): number => {
  const pages = usePortalEditorStore.getState().portalData?.pages as PortalPage[] | undefined;
  if (Array.isArray(pages) && pages.length > 0) {
    const hostingUploader = pages.find(
      (page) => page.elements?.some((element) => element.kind === "uploader")
    );
    return (hostingUploader ?? pages[0]).pageNumber;
  }
  return 1;
};

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
  // It defaults to the selected connector's configured prefix (or the bucket
  // root) so the admin can add a destination without browsing; `rootPathTouched`
  // tracks whether the user has explicitly browsed to a folder, so switching
  // connectors won't clobber a manual choice.
  const [rootPath, setRootPath] = useState(destination?.rootPath ?? "");
  const [rootPathTouched, setRootPathTouched] = useState(destination?.rootPath !== undefined);
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

  // The prefix to default the root path to when a connector is selected:
  // the connector's first configured objectPrefix, or "" (bucket root).
  const selectedConnector = useMemo(
    () => connectors.find((c) => c.id === connectorId),
    [connectors, connectorId]
  );
  const connectorPrefix = useMemo(() => {
    const op = (selectedConnector as { objectPrefix?: string | string[] } | undefined)
      ?.objectPrefix;
    if (Array.isArray(op)) return op[0] ?? "";
    if (typeof op === "string") return op;
    return "";
  }, [selectedConnector]);

  // When the selected connector changes, default the root path to that
  // connector's prefix (or bucket root) unless the user has explicitly browsed
  // to a folder. Mounting with an existing destination's connector does not
  // re-default (prev === current), so a saved root path is preserved.
  const prevConnectorRef = useRef(connectorId);
  useEffect(() => {
    if (prevConnectorRef.current === connectorId) return;
    prevConnectorRef.current = connectorId;
    if (!rootPathTouched) {
      setRootPath(connectorPrefix);
    }
  }, [connectorId, connectorPrefix, rootPathTouched]);

  const handleSave = () => {
    const newErrors: Record<string, string> = {};
    if (!friendlyName.trim()) newErrors.friendlyName = "Friendly name is required";
    if (!connectorId) newErrors.connectorId = "Connector is required";
    // Root path "" (empty string) is valid — it means the bucket root — and is
    // defaulted from the connector, so it never blocks saving.
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
      // Always reference a real page. Preserve an existing assignment when
      // editing; otherwise default to the uploader's page (page 1 in the
      // single-page default). Prevents the server "unknown page None" error.
      pageNumber: destination?.pageNumber ?? resolveUploaderPageNumber(),
      ...(structuredPathMode ? { pathSegments: toApiSegments(pathSegments), pathSeparator } : {}),
    });
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        // Top padding so the first field's floating label ("Friendly Name")
        // isn't clipped by the dialog title above it.
        pt: 1,
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
          value={rootPath || "/"}
          size="small"
          fullWidth
          slotProps={{ input: { readOnly: true } }}
          error={!!errors.rootPath}
          helperText={
            errors.rootPath ?? (rootPath ? undefined : "Bucket root (browse to choose a folder)")
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
        <Button variant="contained" onClick={handleSave} disabled={!friendlyName || !connectorId}>
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
            setRootPathTouched(true);
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
