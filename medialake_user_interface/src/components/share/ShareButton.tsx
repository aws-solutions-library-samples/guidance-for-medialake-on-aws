import React, { useState } from "react";
import { IconButton, Tooltip } from "@mui/material";
import ShareIcon from "@mui/icons-material/Share";
import { ShareDialog } from "./ShareDialog";

interface ShareButtonProps {
  assetId: string;
  assetName?: string;
}

export const ShareButton: React.FC<ShareButtonProps> = ({ assetId, assetName }) => {
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDialogOpen(true);
  };

  const handleClose = () => {
    setDialogOpen(false);
  };

  return (
    <>
      <Tooltip title="Share this asset">
        <IconButton
          size="small"
          onClick={handleClick}
          sx={{
            color: "action.active",
            "&:hover": {
              color: "primary.main",
            },
          }}
        >
          <ShareIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <ShareDialog
        open={dialogOpen}
        onClose={handleClose}
        assetId={assetId}
        assetName={assetName}
      />
    </>
  );
};
