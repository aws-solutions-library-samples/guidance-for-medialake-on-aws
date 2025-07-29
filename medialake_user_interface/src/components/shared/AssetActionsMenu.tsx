import React from "react";
import { Menu, MenuItem, CircularProgress, Box } from "@mui/material";
import { type AssetBase } from "../../types/search/searchResults";

interface AssetActionsMenuProps<T extends AssetBase> {
  anchorEl: HTMLElement | null;
  selectedAsset: T | null;
  onClose: () => void;
  onAction: (action: string) => void;
  isLoading: {
    download: boolean;
    [key: string]: boolean;
  };
  actions?: Array<{
    id: string;
    label: string;
  }>;
}

const defaultActions = [
  { id: "rename", label: "Rename" },
  { id: "download", label: "Download" },
];

function AssetActionsMenu<T extends AssetBase>({
  anchorEl,
  selectedAsset,
  onClose,
  onAction,
  actions = defaultActions,
  isLoading,
}: AssetActionsMenuProps<T>) {
  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      onClick={(e) => e.stopPropagation()}
      transformOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
      anchorOrigin={{
        vertical: "bottom",
        horizontal: "right",
      }}
    >
      {actions.map((action) => (
        <MenuItem
          key={action.id}
          onClick={() => onAction(action.id)}
          disabled={
            !selectedAsset || (action.id === "download" && isLoading.download)
          }
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {action.label}
            {action.id === "download" && isLoading.download && (
              <CircularProgress size={16} />
            )}
          </Box>
        </MenuItem>
      ))}
    </Menu>
  );
}

export default AssetActionsMenu;
