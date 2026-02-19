import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
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
  Select,
  MenuItem,
  FormControl,
  Collapse,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import VideocamOutlinedIcon from "@mui/icons-material/VideocamOutlined";
import AudiotrackOutlinedIcon from "@mui/icons-material/AudiotrackOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import { useRightSidebar } from "./SidebarContext";
import { useGetPipelines } from "@/features/pipelines/api/pipelinesController";

interface BatchOperationsProps {
  selectedAssets: Array<{
    id: string;
    name: string;
    type: string;
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
}

const getAssetTypeIcon = (type: string) => {
  const t = type.toLowerCase();
  if (t.includes("image") || t.includes("photo")) return <ImageOutlinedIcon fontSize="small" />;
  if (t.includes("video")) return <VideocamOutlinedIcon fontSize="small" />;
  if (t.includes("audio")) return <AudiotrackOutlinedIcon fontSize="small" />;
  return <InsertDriveFileOutlinedIcon fontSize="small" />;
};

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
}) => {
  const { t } = useTranslation();
  const { setHasSelectedItems } = useRightSidebar();
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>("");
  const [collapsedTypes, setCollapsedTypes] = useState<Record<string, boolean>>({});
  const { data: pipelinesData, isLoading: isPipelinesLoading } = useGetPipelines();

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

  const handlePipelineRun = () => {
    if (!selectedPipelineId) return;
    const pipeline = filteredManualPipelines.find((p) => p.id === selectedPipelineId);
    if (!pipeline) return;

    if (onBatchPipelineExecutionRequest) {
      onBatchPipelineExecutionRequest(pipeline.id, pipeline.name);
    } else if (onBatchPipelineExecution) {
      onBatchPipelineExecution(pipeline.id);
    }
  };

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
      grouped[type].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" })
      );
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

  if (selectedAssets.length === 0) {
    return null;
  }

  const hasPipelines = filteredManualPipelines.length > 0;

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* ── Header: count + quick actions ── */}
      <Box
        sx={{
          px: 2,
          pt: 2,
          pb: 1.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
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

        {/* Compact action icons */}
        <Box sx={{ display: "flex", gap: 0.25 }}>
          <Tooltip title={t("common.actions.downloadSelected")} arrow>
            <span>
              <IconButton
                size="small"
                onClick={onBatchDownload}
                disabled={isDownloadLoading}
                sx={{
                  color: "text.secondary",
                  "&:hover": {
                    color: "primary.main",
                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08),
                  },
                }}
              >
                {isDownloadLoading ? (
                  <CircularProgress size={18} />
                ) : (
                  <FileDownloadOutlinedIcon fontSize="small" />
                )}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={t("common.batchOperations.deleteSelected")} arrow>
            <span>
              <IconButton
                size="small"
                data-testid="batch-delete-button"
                onClick={() => onBatchDelete?.()}
                disabled={isDeleteLoading || !onBatchDelete}
                sx={{
                  color: "text.secondary",
                  "&:hover": {
                    color: "error.main",
                    bgcolor: (theme) => alpha(theme.palette.error.main, 0.08),
                  },
                }}
              >
                {isDeleteLoading ? (
                  <CircularProgress size={18} />
                ) : (
                  <DeleteOutlineIcon fontSize="small" />
                )}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Pipeline execution row ── */}
      {(hasPipelines || isPipelinesLoading) && (
        <Box
          sx={{
            mx: 2,
            mb: 1.5,
            p: 1.25,
            borderRadius: 2,
            bgcolor: (theme) => alpha(theme.palette.primary.main, 0.04),
            border: "1px solid",
            borderColor: (theme) => alpha(theme.palette.primary.main, 0.12),
          }}
        >
          <Typography
            variant="caption"
            sx={{
              display: "block",
              mb: 0.75,
              fontWeight: 600,
              color: "text.secondary",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontSize: "0.65rem",
            }}
          >
            {t("common.batchOperations.runPipeline")}
          </Typography>
          <Box sx={{ display: "flex", gap: 0.75, alignItems: "center" }}>
            <FormControl size="small" sx={{ flex: 1, minWidth: 0 }}>
              <Select
                value={selectedPipelineId}
                onChange={(e) => setSelectedPipelineId(e.target.value)}
                displayEmpty
                disabled={isPipelinesLoading || filteredManualPipelines.length === 0}
                sx={{
                  fontSize: "0.8125rem",
                  bgcolor: "background.paper",
                  "& .MuiSelect-select": {
                    py: 0.75,
                    px: 1.25,
                  },
                  "& .MuiOutlinedInput-notchedOutline": {
                    borderColor: (theme) => alpha(theme.palette.divider, 0.6),
                  },
                }}
              >
                <MenuItem value="" disabled>
                  <Typography variant="body2" color="text.secondary">
                    {isPipelinesLoading
                      ? t("common.batchOperations.pipelineLoading")
                      : t("common.batchOperations.selectPipeline")}
                  </Typography>
                </MenuItem>
                {filteredManualPipelines.map((pipeline) => (
                  <MenuItem key={pipeline.id} value={pipeline.id}>
                    <Typography variant="body2" noWrap>
                      {pipeline.name}
                    </Typography>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Tooltip title={t("common.actions.executePipeline")} arrow>
              <span>
                <IconButton
                  size="small"
                  onClick={handlePipelineRun}
                  disabled={!selectedPipelineId || isPipelineExecutionLoading}
                  sx={{
                    bgcolor: "primary.main",
                    color: "primary.contrastText",
                    width: 32,
                    height: 32,
                    flexShrink: 0,
                    "&:hover": { bgcolor: "primary.dark" },
                    "&.Mui-disabled": {
                      bgcolor: "action.disabledBackground",
                      color: "action.disabled",
                    },
                  }}
                >
                  {isPipelineExecutionLoading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <PlayArrowRoundedIcon fontSize="small" />
                  )}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
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
                        title={asset.name}
                        disableHoverListener={asset.name.length < 50}
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
    </Box>
  );
};

export default BatchOperations;
