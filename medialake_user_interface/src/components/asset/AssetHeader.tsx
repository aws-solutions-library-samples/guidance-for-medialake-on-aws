import React from "react";
import { useTranslation } from "react-i18next";
import { Box, IconButton, Tooltip } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import HomeIcon from "@mui/icons-material/Home";
import LockIcon from "@mui/icons-material/Lock";
import RestoreIcon from "@mui/icons-material/Restore";
import { zIndexTokens } from "@/theme/tokens";
import { useCollectionAssetPermissions } from "@/permissions";

interface AssetHeaderProps {
  onDownload?: () => void;
  onAddToCollection?: () => void;
  onLock?: () => void;
  onRestore?: () => void;
}

const AssetHeader: React.FC<AssetHeaderProps> = ({
  onDownload,
  onAddToCollection,
  onLock,
  onRestore,
}) => {
  const { t } = useTranslation();
  const { canAdd, addTooltip } = useCollectionAssetPermissions();

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "flex-end",
        gap: 1,
        p: 1,
        bgcolor: "background.paper",
        borderRadius: 1,
        position: "sticky",
        top: 64, // Below breadcrumb
        zIndex: zIndexTokens.stickyHeader,
      }}
    >
      <Tooltip title={t("common.actions.download")}>
        <IconButton onClick={onDownload}>
          <DownloadIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title={canAdd ? t("common.actions.addToCollection") : addTooltip}>
        <span>
          <IconButton onClick={onAddToCollection} disabled={!canAdd}>
            <HomeIcon />
          </IconButton>
        </span>
      </Tooltip>

      <Tooltip title={t("common.actions.lock")}>
        <IconButton onClick={onLock}>
          <LockIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title={t("common.actions.restore")}>
        <IconButton onClick={onRestore}>
          <RestoreIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default AssetHeader;
