import React from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Button,
  IconButton,
  Tooltip,
  CircularProgress,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
// import ShareIcon from "@mui/icons-material/Share";
import { useRightSidebar } from "./SidebarContext";

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
}

const BatchOperations: React.FC<BatchOperationsProps> = ({
  selectedAssets,
  onBatchDelete,
  onBatchDownload,

  onClearSelection,
  onRemoveItem,
  isDownloadLoading = false,
  isDeleteLoading = false,
}) => {
  const { t } = useTranslation();
  const { setHasSelectedItems } = useRightSidebar();

  // Update selected items state
  React.useEffect(() => {
    if (selectedAssets.length > 0) {
      console.log(
        "BatchOperations: Setting selected items state for",
        selectedAssets.length,
        "selected assets"
      );
      setHasSelectedItems(true);
    } else {
      setHasSelectedItems(false);
    }
  }, [selectedAssets.length, setHasSelectedItems]);

  // Group assets by type
  const assetsByType = React.useMemo(() => {
    return selectedAssets.reduce(
      (acc, asset) => {
        if (!acc[asset.type]) {
          acc[asset.type] = [];
        }
        acc[asset.type].push(asset);
        return acc;
      },
      {} as Record<string, typeof selectedAssets>
    );
  }, [selectedAssets]);

  // Handle removing a single item
  const handleRemoveItem = (assetId: string) => {
    if (onRemoveItem) {
      onRemoveItem(assetId);
    } else if (onClearSelection) {
      // Fall back to clearing all if specific handler not provided
      console.log("No specific item removal handler provided, clearing all");
      onClearSelection();
    }
  };

  // Don't render anything if no assets are selected
  if (selectedAssets.length === 0) {
    return null;
  }

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Action buttons */}
      <Box
        sx={{
          display: "flex",
          gap: 1.5,
          p: 2,
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Tooltip title={t("common.batchOperations.deleteSelected")}>
          <Button
            variant="contained"
            size="small"
            data-testid="batch-delete-button"
            startIcon={isDeleteLoading ? <CircularProgress size={16} /> : <DeleteIcon />}
            onClick={() => {
              console.log("Delete button clicked, onBatchDelete:", onBatchDelete);
              if (onBatchDelete) {
                onBatchDelete();
              }
            }}
            disabled={isDeleteLoading || !onBatchDelete}
            sx={{
              bgcolor: "error.main",
              color: "white",
              "&:hover": {
                bgcolor: "error.dark",
              },
              "&:disabled": {
                bgcolor: "action.disabledBackground",
              },
            }}
          >
            {isDeleteLoading ? t("common.actions.deleting") : t("common.actions.delete")}
          </Button>
        </Tooltip>
        <Tooltip title={t("common.actions.downloadSelected")}>
          <Button
            variant="outlined"
            size="small"
            startIcon={isDownloadLoading ? <CircularProgress size={16} /> : <DownloadIcon />}
            onClick={onBatchDownload}
            disabled={isDownloadLoading}
          >
            {isDownloadLoading ? "Starting..." : "Download"}
          </Button>
        </Tooltip>
        {/* i18n-ignore - commented out code
        <Tooltip title="Share selected">
          <Button
            variant="outlined"
            size="small"
            startIcon={<ShareIcon />}
            onClick={onBatchShare}
          >
            Share
          </Button>
        </Tooltip>
        */}
      </Box>

      {/* Selected items list */}
      <Box sx={{ flexGrow: 1, overflow: "auto" }}>
        {Object.entries(assetsByType).map(([type, assets]) => (
          <Box key={type}>
            <Typography
              variant="subtitle2"
              sx={{
                px: 2,
                py: 1,
                bgcolor: "background.default",
                fontWeight: 600,
              }}
            >
              {type} ({assets.length})
            </Typography>
            <List dense disablePadding>
              {assets.map((asset) => (
                <ListItem
                  key={asset.id}
                  secondaryAction={
                    <IconButton
                      edge="end"
                      size="small"
                      onClick={() => handleRemoveItem(asset.id)}
                      title={t("common.actions.removeItem")}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  }
                  sx={{
                    px: 2,
                    "&:hover": {
                      bgcolor: "action.hover",
                    },
                  }}
                >
                  <ListItemText
                    primary={asset.name}
                    primaryTypographyProps={{
                      variant: "body2",
                      noWrap: true,
                      title: asset.name,
                    }}
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        ))}
      </Box>

      {/* Clear selection button */}
      <Box
        sx={{
          p: 2,
          textAlign: "center",
          borderTop: "1px solid",
          borderColor: "divider",
        }}
      >
        <Button variant="text" size="small" onClick={onClearSelection}>
          Clear Selection
        </Button>
      </Box>
    </Box>
  );
};

export default BatchOperations;
