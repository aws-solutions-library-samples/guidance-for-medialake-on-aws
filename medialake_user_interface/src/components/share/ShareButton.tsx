import React, { useState } from "react";
import { IconButton, Tooltip } from "@mui/material";
import ShareIcon from "@mui/icons-material/Share";
import { ShareDialog } from "./ShareDialog";

interface ShareButtonProps {
  assetId: string;
  assetName?: string;
  variant?: "icon" | "button";
  onShareCreated?: (shareUrl: string) => void;
}

export const ShareButton: React.FC<ShareButtonProps> = ({
  assetId,
  assetName,
  variant = "icon",
  onShareCreated,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDialogOpen(true);
  };

  const handleClose = () => {
    setDialogOpen(false);
  };

  const handleShareCreated = (shareUrl: string) => {
    if (onShareCreated) {
      onShareCreated(shareUrl);
    }
  };

  if (variant === "icon") {
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
  }

  return null;
};
