import React from "react";
import { useTranslation } from "react-i18next";
import { Box, IconButton, Tooltip } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import HomeIcon from "@mui/icons-material/Home";
import LockIcon from "@mui/icons-material/Lock";
import RestoreIcon from "@mui/icons-material/Restore";

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
        zIndex: 1000,
      }}
    >
      <Tooltip title={t("common.actions.download")}>
        <IconButton onClick={onDownload}>
          <DownloadIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title={t("common.actions.addToCollection")}>
        <IconButton onClick={onAddToCollection}>
          <HomeIcon />
        </IconButton>
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
