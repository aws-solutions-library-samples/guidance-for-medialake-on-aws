/**
 * AssetCardCollectionBadge — folder icon (top-right of thumbnail) shown when the asset
 * is in at least one collection.
 */
import React from "react";
import { Box, Tooltip } from "@mui/material";
import { alpha } from "@mui/material/styles";
import FolderIcon from "@mui/icons-material/Folder";
import { useTranslation } from "react-i18next";

interface AssetCardCollectionBadgeProps {
  visible: boolean;
}

const AssetCardCollectionBadge: React.FC<AssetCardCollectionBadgeProps> = React.memo(
  ({ visible }) => {
    const { t } = useTranslation();
    if (!visible) return null;
    const label = t("assets.inCollection", { defaultValue: "In a collection" });
    return (
      <Tooltip title={label}>
        <Box
          role="img"
          aria-label={label}
          sx={(theme) => ({
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            p: 0.5,
            borderRadius: 1,
            color: "primary.main",
            bgcolor: alpha(theme.palette.background.paper, 0.85),
          })}
        >
          <FolderIcon fontSize="small" />
        </Box>
      </Tooltip>
    );
  }
);

AssetCardCollectionBadge.displayName = "AssetCardCollectionBadge";
export default AssetCardCollectionBadge;
