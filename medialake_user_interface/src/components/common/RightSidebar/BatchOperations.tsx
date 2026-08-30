import React, { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSnackbar } from "notistack";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
  CircularProgress,
  Chip,
  Collapse,
  Button,
} from "@mui/material";
import { alpha, type Theme } from "@mui/material/styles";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
// Quick Access is disabled for now — see the commented-out block below.
// import StarRoundedIcon from "@mui/icons-material/StarRounded";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import CreateNewFolderOutlinedIcon from "@mui/icons-material/CreateNewFolderOutlined";
import FolderOutlinedIcon from "@mui/icons-material/FolderOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import VideocamOutlinedIcon from "@mui/icons-material/VideocamOutlined";
import AudiotrackOutlinedIcon from "@mui/icons-material/AudiotrackOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import { useRightSidebar } from "./SidebarContext";
import { useGetPipelinesOptional } from "@/features/pipelines/api/pipelinesController";
import { useActionPermission } from "@/permissions/hooks/useActionPermission";
import { useCollectionAssetPermissions } from "@/permissions/hooks/useCollectionAssetPermissions";
import {
  useAddItemToCollection,
  resolveAddedCount,
  type AddCollectionItemSpec,
} from "@/api/hooks/useCollections";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import WorkflowPickerModal, {
  type WorkflowPickerItem,
} from "@/components/pipelines/WorkflowPickerModal";
import { segmentToClipBoundary } from "@/hooks/useAssetSelection";
import { useRecentBinActions } from "@/hooks/useRecentBinActions";
import { accentColor, type AccentRole } from "@/theme/accessibleAccent";
import { formatTimeRange } from "@/utils/timecode";

/**
 * How many entries the Quick Access row shows, across both kinds.
 * Unused while Quick Access is commented out below.
 */
// const QUICK_ACCESS_LIMIT = 3;

interface BatchOperationsProps {
  selectedAssets: Array<{
    id: string;
    name: string;
    type: string;
    inventoryID?: string;
    segment?: BinSegment;
  }>;
  onBatchDelete?: () => void;
  onBatchDownload?: () => void;
  onBatchShare?: () => void;
  onClearSelection?: () => void;
  onRemoveItem?: (assetId: string) => void;
  isDownloadLoading?: boolean;
  isDeleteLoading?: boolean;
  onBatchPipelineExecution?: (pipelineId: string) => void;
  onBatchPipelineExecutionRequest?: (pipelineId: string, pipelineName: string) => void;
  isPipelineExecutionLoading?: boolean;
  canDelete?: boolean;
}

const getAssetTypeIcon = (type: string) => {
  const t = type.toLowerCase();
  if (t.includes("image") || t.includes("photo")) return <ImageOutlinedIcon fontSize="small" />;
  if (t.includes("video")) return <VideocamOutlinedIcon fontSize="small" />;
  if (t.includes("audio")) return <AudiotrackOutlinedIcon fontSize="small" />;
  return <InsertDriveFileOutlinedIcon fontSize="small" />;
};

/** A bin entry's segment, when the entry is a clip rather than a whole asset. */
type BinSegment = { startTime: number; endTime: number; label?: string };

/**
 * The time range shown for a segment (clip) bin entry, or null for a whole
 * asset.
 *
 * Delegates to the shared timecode formatter so the range reads identically
 * here, in the add-to-collection modal and in a collection listing. The local
 * `m:ss` formatter this replaces had no hours carry, so a clip an hour into an
 * asset rendered as "65:00".
 */
const segmentRange = (segment?: BinSegment): string | null =>
  segment ? formatTimeRange(segment.startTime, segment.endTime) : null;

// Display name for a bin entry; appends the time range for segment entries so
// multiple segments of the same asset are distinguishable.
const displayNameFor = (asset: { name: string; segment?: BinSegment }): string => {
  const range = segmentRange(asset.segment);
  const label = asset.segment?.label?.trim();

  if (!range) return asset.name;
  return label ? `${asset.name} (${range} · ${label})` : `${asset.name} (${range})`;
};

/**
 * A collection that has been deleted (or unshared) still lives in the recents
 * store until we learn otherwise. The API answers 404 in that case, which is
 * our signal to drop the stale shortcut rather than leave a chip that can never
 * succeed.
 */
const isNotFoundError = (error: unknown): boolean =>
  typeof error === "object" &&
  error !== null &&
  (error as { response?: { status?: number } }).response?.status === 404;

const BatchOperations: React.FC<BatchOperationsProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,
  onClearSelection,
  onRemoveItem,
  isDownloadLoading = false,
  isDeleteLoading = false,
  onBatchPipelineExecution,
  onBatchPipelineExecutionRequest,
  isPipelineExecutionLoading = false,
  canDelete = true,
}) => {
  const { t } = useTranslation();
  const { setHasSelectedItems } = useRightSidebar();
  const { enqueueSnackbar } = useSnackbar();
  const [collapsedTypes, setCollapsedTypes] = useState<Record<string, boolean>>({});

  const [isWorkflowModalOpen, setIsWorkflowModalOpen] = useState(false);
  const [isCollectionModalOpen, setIsCollectionModalOpen] = useState(false);
  const [isAddingToCollection, setIsAddingToCollection] = useState(false);

  // Pipelines are an optional add-on in the sidebar: everything else here
  // (download, delete, collections, the selected-items list) must keep working
  // for users who have no pipeline access at all.
  //
  // Running a pipeline on the selection needs BOTH:
  //   - list  → GET  /pipelines                        → pipelines:view → can("view", "pipeline")
  //   - run   → POST /pipelines/{id}/trigger           → pipelines:edit → can("edit", "pipeline")
  //
  // If either is missing we hide the pipeline UI and never issue the request,
  // otherwise the 403 from GET /pipelines trips the global access-denied
  // redirect and throws the user off the page just for opening the sidebar.
  // `useActionPermission` reports allowed === false while the ability is still
  // loading, so the query stays disabled until permissions resolve — no 403 and
  // no flash of pipeline UI.
  const canListPipelines = useActionPermission("view", "pipeline").allowed;
  const canRunPipelines = useActionPermission("edit", "pipeline").allowed;
  const canUsePipelines = canListPipelines && canRunPipelines;

  // Bulk download hits POST /download/bulk, which requires `assets:download`.
  // Same story as pipelines: without the permission the click would 403 and
  // bounce the user to /access-denied, so hide the button instead.
  const canDownload = useActionPermission("download", "asset").allowed;

  // POST /collections/{id}/items accepts `collections:add_assets` OR the broader
  // `collections:edit`; this hook encodes that same OR so the button only shows
  // when the request would actually be authorized.
  const { canAdd: canAddToCollections } = useCollectionAssetPermissions();

  // `canDelete` is supplied by the parent (it already derives it from
  // useActionPermission("delete", "asset")) so per-page overrides keep working.

  const { data: pipelinesData, isLoading: isPipelinesLoading } = useGetPipelinesOptional({
    enabled: canUsePipelines,
  });

  // Only `recordUse` is live: usage is still recorded so the commented-out Quick
  // Access row works the moment it is switched back on. `recents` and `forget`
  // are read by that block alone, so they are left out of the destructure until
  // then rather than sitting here unused.
  const { recordUse } = useRecentBinActions();
  const addItemToCollectionMutation = useAddItemToCollection();

  // Filter manual pipelines based on selected asset types
  const filteredManualPipelines = useMemo(() => {
    if (!pipelinesData?.data?.s) return [];

    const selectedAssetTypes = Array.from(new Set(selectedAssets.map((a) => a.type))) as string[];

    return pipelinesData.data.s.filter((pipeline) => {
      if (!pipeline.type?.includes("Manual Trigger")) return false;

      const manualTriggerNode = pipeline.definition?.nodes?.find(
        (node) => node.data?.nodeId === "trigger_manual"
      );

      const supportedTypes =
        manualTriggerNode?.data?.configuration?.parameters?.["Supported Content Types"];

      if (!supportedTypes || !Array.isArray(supportedTypes) || supportedTypes.length === 0) {
        return true;
      }

      return selectedAssetTypes.some((assetType) =>
        supportedTypes.some((supported: unknown) => {
          const s = String(supported).toLowerCase();
          return assetType.toLowerCase() === s || assetType.toLowerCase().startsWith(s);
        })
      );
    });
  }, [pipelinesData, selectedAssets]);

  /** Eligible workflows in the narrow shape the picker and menus need. */
  const availableWorkflows = useMemo<WorkflowPickerItem[]>(
    () =>
      filteredManualPipelines.map((p) => ({
        id: p.id,
        name: p.name,
        description: p.description,
        createdAt: p.createdAt,
      })),
    [filteredManualPipelines]
  );

  /**
   * Quick Access — DISABLED FOR NOW.
   *
   * Kept intact (rather than deleted) so it can be switched back on: it is the
   * MRU across both kinds, filtered down to entries the user can actually act on
   * right now — collections need add permission, workflows need pipeline
   * permission *and* must still exist and accept the selected asset types, since
   * a shortcut that would fail on click is worse than no shortcut.
   *
   * The recents store itself stays in use: the Workflow and Collection dropdowns
   * below still read from it.
   */
  // const quickAccess = useMemo(() => {
  //   const workflowsById = new Map(availableWorkflows.map((w) => [w.id, w]));
  //   return recents
  //     .filter((entry) => {
  //       if (entry.kind === "collection") return canAddToCollections;
  //       return canUsePipelines && workflowsById.has(entry.id);
  //     })
  //     .slice(0, QUICK_ACCESS_LIMIT)
  //     .map((entry) => ({
  //       ...entry,
  //       // Prefer the live name for workflows — a rename should be reflected.
  //       name:
  //         entry.kind === "workflow"
  //           ? (workflowsById.get(entry.id)?.name ?? entry.name)
  //           : entry.name,
  //     }));
  // }, [recents, availableWorkflows, canAddToCollections, canUsePipelines]);

  // Update selected items state
  React.useEffect(() => {
    if (selectedAssets.length > 0) {
      setHasSelectedItems(true);
    } else {
      setHasSelectedItems(false);
    }
  }, [selectedAssets.length, setHasSelectedItems]);

  // Group assets by type, then sort by type and by name within each group
  const assetsByType = useMemo(() => {
    const grouped = selectedAssets.reduce(
      (acc, asset) => {
        if (!acc[asset.type]) {
          acc[asset.type] = [];
        }
        acc[asset.type].push(asset);
        return acc;
      },
      {} as Record<string, typeof selectedAssets>
    );

    for (const type of Object.keys(grouped)) {
      grouped[type].sort((a, b) => {
        const byName = a.name.localeCompare(b.name, undefined, {
          numeric: true,
          sensitivity: "base",
        });
        if (byName !== 0) return byName;

        // Several clips of one asset share a name, so name comparison leaves
        // them in arbitrary order. Order those chronologically instead —
        // reading a clip list out of time order is disorienting.
        return (a.segment?.startTime ?? 0) - (b.segment?.startTime ?? 0);
      });
    }

    return grouped;
  }, [selectedAssets]);

  const sortedTypes = useMemo(
    () =>
      Object.keys(assetsByType).sort((a, b) =>
        a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" })
      ),
    [assetsByType]
  );

  const handleRemoveItem = (assetId: string) => {
    if (onRemoveItem) {
      onRemoveItem(assetId);
    } else if (onClearSelection) {
      onClearSelection();
    }
  };

  const toggleTypeCollapse = (type: string) => {
    setCollapsedTypes((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  const runWorkflow = useCallback(
    (workflow: WorkflowPickerItem) => {
      if (!canUsePipelines) return;
      recordUse("workflow", workflow.id, workflow.name);
      setIsWorkflowModalOpen(false);

      // Prefer the confirm-dialog path so the user still gets the execution
      // options (output packaging) they'd get from the old select-and-run row.
      if (onBatchPipelineExecutionRequest) {
        onBatchPipelineExecutionRequest(workflow.id, workflow.name);
      } else {
        onBatchPipelineExecution?.(workflow.id);
      }
    },
    [canUsePipelines, recordUse, onBatchPipelineExecutionRequest, onBatchPipelineExecution]
  );

  /**
   * Add the whole selection to a collection in one request.
   *
   * Segment (clip) entries carry their own boundary so a bin holding both a full
   * asset and two of its clips stores three distinct items — the same rule the
   * bulk-download path follows. Throws on failure so the modal can surface the
   * message inline; the menu/chip callers catch it themselves.
   */
  const addSelectionToCollection = useCallback(
    async (collectionId: string, collectionName?: string) => {
      if (!canAddToCollections || selectedAssets.length === 0) return;

      const items: AddCollectionItemSpec[] = selectedAssets.map((asset) => ({
        assetId: asset.inventoryID || asset.id,
        clipBoundary: asset.segment ? segmentToClipBoundary(asset.segment) : undefined,
      }));

      setIsAddingToCollection(true);
      try {
        const response = await addItemToCollectionMutation.mutateAsync({
          collectionId,
          data: { items },
        });

        const label =
          collectionName?.trim() || t("common.batchOperations.collection", "Collection");
        recordUse("collection", collectionId, label);

        const added = resolveAddedCount(response, { items });
        const alreadyPresent = response?.data?.alreadyPresentCount ?? 0;

        // The add endpoint is quiet on its own, and the modal closes on success,
        // so without this the user gets no confirmation that anything happened.
        if (added > 0) {
          enqueueSnackbar(
            t("common.batchOperations.addedToCollection", "Added {{count}} to {{name}}", {
              count: added,
              name: label,
            }),
            { variant: "success" }
          );
        } else {
          enqueueSnackbar(
            t("common.batchOperations.alreadyInCollection", "{{count}} already in {{name}}", {
              count: alreadyPresent || items.length,
              name: label,
            }),
            { variant: "info" }
          );
        }
      } finally {
        setIsAddingToCollection(false);
      }
    },
    [
      canAddToCollections,
      selectedAssets,
      addItemToCollectionMutation,
      recordUse,
      enqueueSnackbar,
      t,
    ]
  );

  // Shortcut path for acting on a remembered target without opening the picker.
  // Disabled with Quick Access below; the pickers are the only live entry points.
  // /** Menu/chip path: swallow the error (the hook already surfaced it) and drop dead shortcuts. */
  // const addToCollectionShortcut = useCallback(
  //   async (collectionId: string, collectionName: string) => {
  //     try {
  //       await addSelectionToCollection(collectionId, collectionName);
  //     } catch (error) {
  //       if (isNotFoundError(error)) {
  //         forget("collection", collectionId);
  //       }
  //     }
  //   },
  //   [addSelectionToCollection, forget]
  // );

  // Quick Access click handler — disabled along with the row above.
  // const handleQuickAccessClick = useCallback(
  //   (entry: { kind: "collection" | "workflow"; id: string; name: string }) => {
  //     if (entry.kind === "workflow") {
  //       const workflow = availableWorkflows.find((w) => w.id === entry.id);
  //       if (workflow) runWorkflow(workflow);
  //       return;
  //     }
  //     void addToCollectionShortcut(entry.id, entry.name);
  //   },
  //   [availableWorkflows, runWorkflow, addToCollectionShortcut]
  // );

  if (selectedAssets.length === 0) {
    return null;
  }

  const hasPipelines = filteredManualPipelines.length > 0;
  // The workflow control is only meaningful when there is (or may still be) a
  // compatible pipeline to run — otherwise the picker would open empty, so the
  // control is omitted rather than shown dead.
  const showWorkflowAction = canUsePipelines && (hasPipelines || isPipelinesLoading);

  // Two explicit rows: the "choose a target" actions, then the direct actions.
  const pickerRowCount = (showWorkflowAction ? 1 : 0) + (canAddToCollections ? 1 : 0);
  const directRowCount = (canDownload ? 1 : 0) + (canDelete ? 1 : 0);
  const hasAnyAction = pickerRowCount + directRowCount > 0;

  const workflowsBusy = isPipelineExecutionLoading;
  const collectionsBusy = isAddingToCollection;

  /**
   * One action, one button, one click — it opens the relevant picker modal.
   *
   * There used to be a dropdown arrow next to the label offering recent targets.
   * It cost ~28px of every control, which is what forced labels to ellipsise
   * ("Wo…" / "Col…") when several shared a row. The shortcut lists live inside the
   * modals instead, so the full label always has room: two controls fit a row at
   * the 375px default and each still reads correctly at the 275px drag minimum.
   */
  const renderAction = (opts: {
    key: string;
    label: string;
    icon: React.ReactNode;
    /** Palette entry driving text/border/hover tint. */
    paletteKey: AccentRole;
    onClick: () => void;
    busy: boolean;
    disabled?: boolean;
    testId: string;
  }) => (
    <Button
      key={opts.key}
      variant="outlined"
      size="small"
      onClick={opts.onClick}
      disabled={opts.busy || opts.disabled}
      data-testid={opts.testId}
      startIcon={opts.busy ? <CircularProgress size={14} color="inherit" /> : opts.icon}
      sx={(theme) => {
        const c = accentColor(theme, opts.paletteKey);
        const isDark = theme.palette.mode === "dark";
        return {
          // 130px basis: with ~38px of chrome (borders, padding, icon) two
          // controls share a row at the default width with ~129px for the label —
          // more than the longest translation needs (pt "Fluxo de trabalho" ≈
          // 93px). At the 275px minimum the pair no longer fits, so the row wraps
          // to one full-width control each rather than truncating.
          flex: "1 1 130px",
          minWidth: 0,
          px: 1,
          py: 0.6,
          justifyContent: "flex-start",
          textTransform: "none",
          fontSize: "0.78rem",
          fontWeight: 600,
          borderRadius: 2,
          color: c,
          // Borders are non-text UI, so they answer to WCAG 1.4.11 (3:1) rather
          // than 4.5:1. The old 0.4 alpha measured ~1.9:1 in light mode and
          // ~1.8:1 in dark — effectively invisible outlines. Measured minimums to
          // reach 3:1 are 0.75 light / 0.60 dark, so both are set a touch above.
          borderColor: alpha(c, isDark ? 0.7 : 0.8),
          // Kept shallow on purpose: every percent of tint lightens the surface
          // and eats into the label's contrast ratio.
          bgcolor: alpha(c, 0.04),
          "&:hover": {
            borderColor: c,
            bgcolor: alpha(c, 0.1),
          },
          // Keyboard users get an explicit ring: the tinted hover background
          // alone is far too subtle to serve as a focus indicator.
          "&.Mui-focusVisible": {
            outline: `2px solid ${c}`,
            outlineOffset: 2,
          },
          "& .MuiButton-startIcon": { mr: 0.5, ml: 0 },
          "& .MuiButton-startIcon > *:first-of-type": { fontSize: 16 },
        };
      }}
    >
      <Box
        component="span"
        sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
      >
        {opts.label}
      </Box>
    </Button>
  );

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* ── Header: count + clear ── */}
      <Box
        sx={{
          px: 2,
          pt: 2,
          pb: 1.25,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, letterSpacing: "0.01em" }}>
            {selectedAssets.length}{" "}
            {selectedAssets.length === 1 ? t("common.item") : t("common.items")}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              cursor: "pointer",
              "&:hover": { color: "text.primary" },
            }}
            onClick={onClearSelection}
          >
            {t("common.clear")}
          </Typography>
        </Box>
      </Box>

      {/* ── Quick Access: DISABLED FOR NOW ──
          Most recently used collections / workflows as one-click chips. Left in
          place so it can be re-enabled without rebuilding it; the recents store
          it reads from is still used by the dropdowns below.

      {quickAccess.length > 0 && (
        <Box sx={{ px: 2, pb: 1.25 }} data-testid="bin-quick-access">
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
            <StarRoundedIcon sx={{ fontSize: 15, color: "warning.main" }} />
            <Typography
              variant="caption"
              sx={{
                fontWeight: 600,
                color: "text.secondary",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                fontSize: "0.65rem",
              }}
            >
              {t("common.batchOperations.quickAccess", "Quick Access")}
            </Typography>
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {quickAccess.map((entry) => {
              const paletteKey = entry.kind === "collection" ? "secondary" : "primary";
              const busy = entry.kind === "collection" ? collectionsBusy : workflowsBusy;
              return (
                <Chip
                  key={`${entry.kind}:${entry.id}`}
                  size="small"
                  clickable
                  disabled={busy}
                  onClick={() => handleQuickAccessClick(entry)}
                  icon={
                    entry.kind === "collection" ? (
                      <FolderOutlinedIcon sx={{ fontSize: 14 }} />
                    ) : (
                      <AccountTreeOutlinedIcon sx={{ fontSize: 14 }} />
                    )
                  }
                  label={entry.name}
                  sx={{
                    maxWidth: "100%",
                    height: 26,
                    fontSize: "0.73rem",
                    fontWeight: 500,
                    borderRadius: 2,
                    border: "1px solid",
                    borderColor: (theme) => alpha(theme.palette[paletteKey].main, 0.35),
                    bgcolor: (theme) => alpha(theme.palette[paletteKey].main, 0.06),
                    color: `${paletteKey}.main`,
                    "& .MuiChip-icon": { color: `${paletteKey}.main`, ml: 0.75 },
                    "&:hover": {
                      bgcolor: (theme) => alpha(theme.palette[paletteKey].main, 0.14),
                    },
                  }}
                />
              );
            })}
          </Box>
        </Box>
      )}
      ── end Quick Access ── */}

      {/* ── Primary actions ── */}
      {hasAnyAction && (
        <Box sx={{ px: 2, pb: 1.25, display: "flex", flexDirection: "column", gap: 1 }}>
          {/* Row 1 — pick a target: both open a picker modal. */}
          {pickerRowCount > 0 && (
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }} data-testid="bin-picker-row">
              {showWorkflowAction &&
                renderAction({
                  key: "workflow",
                  label: t("common.batchOperations.workflow", "Workflow"),
                  icon: <AccountTreeOutlinedIcon />,
                  paletteKey: "primary",
                  onClick: () => setIsWorkflowModalOpen(true),
                  busy: workflowsBusy,
                  testId: "batch-workflow-button",
                })}

              {canAddToCollections &&
                renderAction({
                  key: "collection",
                  label: t("common.batchOperations.collection", "Collection"),
                  icon: <CreateNewFolderOutlinedIcon />,
                  paletteKey: "secondary",
                  onClick: () => setIsCollectionModalOpen(true),
                  busy: collectionsBusy,
                  testId: "batch-collection-button",
                })}
            </Box>
          )}

          {/* Row 2 — act on the selection directly, no modal in between.
              Delete keeps error styling so it stays visually distinct from
              Download despite sharing the row. */}
          {directRowCount > 0 && (
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }} data-testid="bin-direct-row">
              {canDownload &&
                renderAction({
                  key: "download",
                  label: t("common.actions.download", "Download"),
                  icon: <FileDownloadOutlinedIcon />,
                  // Neutral would be ideal for a tertiary action, but paired with
                  // Delete on one row the two need to read as clearly different
                  // things, so Download takes the theme primary.
                  paletteKey: "primary",
                  onClick: () => onBatchDownload?.(),
                  busy: isDownloadLoading,
                  disabled: !onBatchDownload,
                  testId: "batch-download-button",
                })}

              {canDelete &&
                renderAction({
                  key: "delete",
                  label: t("common.actions.delete", "Delete"),
                  icon: <DeleteOutlineIcon />,
                  paletteKey: "error",
                  onClick: () => onBatchDelete?.(),
                  busy: isDeleteLoading,
                  disabled: !onBatchDelete,
                  testId: "batch-delete-button",
                })}
            </Box>
          )}
        </Box>
      )}

      {/* ── Divider ── */}
      <Box sx={{ mx: 2, borderBottom: "1px solid", borderColor: "divider" }} />

      {/* ── Selected items list ── */}
      <Box sx={{ flexGrow: 1, overflow: "auto", pt: 0.5 }}>
        {sortedTypes.map((type) => {
          const isCollapsed = collapsedTypes[type] ?? false;
          const count = assetsByType[type].length;

          return (
            <Box key={type}>
              {/* Type group header */}
              <Box
                onClick={() => toggleTypeCollapse(type)}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.75,
                  px: 2,
                  py: 0.75,
                  cursor: "pointer",
                  userSelect: "none",
                  "&:hover": { bgcolor: "action.hover" },
                }}
              >
                <Box sx={{ color: "text.secondary", display: "flex", alignItems: "center" }}>
                  {getAssetTypeIcon(type)}
                </Box>
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 600,
                    color: "text.secondary",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    fontSize: "0.675rem",
                    flex: 1,
                  }}
                >
                  {type}
                </Typography>
                <Chip
                  label={count}
                  size="small"
                  sx={{
                    height: 18,
                    fontSize: "0.675rem",
                    fontWeight: 600,
                    bgcolor: (theme) => alpha(theme.palette.text.primary, 0.06),
                    "& .MuiChip-label": { px: 0.75 },
                  }}
                />
                <Box
                  sx={{
                    color: "text.disabled",
                    display: "flex",
                    alignItems: "center",
                    transition: "transform 0.2s ease",
                    transform: isCollapsed ? "rotate(0deg)" : "rotate(180deg)",
                  }}
                >
                  <ExpandMoreRoundedIcon sx={{ fontSize: 16 }} />
                </Box>
              </Box>

              {/* Collapsible asset list */}
              <Collapse in={!isCollapsed} timeout={200}>
                <List dense disablePadding>
                  {assetsByType[type].map((asset) => (
                    <ListItem
                      key={asset.id}
                      disablePadding
                      secondaryAction={
                        <IconButton
                          edge="end"
                          size="small"
                          onClick={() => handleRemoveItem(asset.id)}
                          title={t("common.actions.removeItem")}
                          sx={{
                            opacity: 0,
                            transition: "opacity 0.15s ease",
                            color: "text.disabled",
                            "&:hover": { color: "error.main" },
                          }}
                        >
                          <CloseRoundedIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                      }
                      sx={{
                        px: 2,
                        pl: 4.5,
                        pr: 5,
                        py: 0.25,
                        "&:hover": {
                          bgcolor: "action.hover",
                          "& .MuiIconButton-root": { opacity: 1 },
                        },
                      }}
                    >
                      <Tooltip
                        title={displayNameFor(asset)}
                        disableHoverListener={displayNameFor(asset).length < 50}
                        enterDelay={400}
                        arrow
                      >
                        <ListItemText
                          primary={asset.name}
                          primaryTypographyProps={{
                            variant: "body2",
                            sx: {
                              fontSize: "0.8125rem",
                              lineHeight: 1.4,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              wordBreak: "break-all",
                            },
                          }}
                          // Segment entries get a dedicated, always-visible line
                          // for their time range so it can't be ellipsized away
                          // by long filenames. The marker label, when the segment
                          // carries one, follows the range on the same line — it
                          // is the only place that label is ever surfaced.
                          secondary={
                            segmentRange(asset.segment)
                              ? [segmentRange(asset.segment), asset.segment?.label?.trim()]
                                  .filter(Boolean)
                                  .join(" \u00b7 ")
                              : undefined
                          }
                          secondaryTypographyProps={{
                            variant: "caption",
                            sx: {
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              // Same reasoning as the action buttons: primary.main
                              // only reaches 2.68:1 on the dark paper, so the clip
                              // timecode was as unreadable as the labels were.
                              color: (theme: Theme) => accentColor(theme, "primary"),
                              fontVariantNumeric: "tabular-nums",
                            },
                          }}
                        />
                      </Tooltip>
                    </ListItem>
                  ))}
                </List>
              </Collapse>
            </Box>
          );
        })}
      </Box>

      {/* ── Modals ── */}
      {canUsePipelines && (
        <WorkflowPickerModal
          open={isWorkflowModalOpen}
          onClose={() => setIsWorkflowModalOpen(false)}
          workflows={availableWorkflows}
          isLoading={isPipelinesLoading}
          selectedCount={selectedAssets.length}
          onRun={runWorkflow}
          isRunning={isPipelineExecutionLoading}
        />
      )}

      {canAddToCollections && isCollectionModalOpen && (
        <AddToCollectionModal
          open={isCollectionModalOpen}
          onClose={() => setIsCollectionModalOpen(false)}
          assetId={selectedAssets[0]?.inventoryID || selectedAssets[0]?.id || ""}
          assetName={t("common.batchOperations.itemsSelected", "{{count}} selected", {
            count: selectedAssets.length,
          })}
          assetType={selectedAssets[0]?.type || ""}
          // Pass the whole selection so the modal can show each clip's time
          // range. The header count alone left several clips of one asset
          // indistinguishable at the point of choosing a destination.
          //
          // Ordered by start time to match the bin listing behind the modal;
          // selection order would show the same three clips in a different
          // order in two panels that are visible at once.
          items={[...selectedAssets]
            .sort(
              (a, b) =>
                a.name.localeCompare(b.name, undefined, {
                  numeric: true,
                  sensitivity: "base",
                }) || (a.segment?.startTime ?? 0) - (b.segment?.startTime ?? 0)
            )
            .map((asset) => ({
              id: asset.id,
              name: asset.name,
              timeRange: segmentRange(asset.segment),
            }))}
          onAddToCollection={addSelectionToCollection}
        />
      )}
    </Box>
  );
};

export default BatchOperations;
