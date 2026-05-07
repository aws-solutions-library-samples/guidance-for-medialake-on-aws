import React from "react";
import { Box, Button, type SxProps, type Theme } from "@mui/material";

interface InlineEditActionsProps {
  preventCommitRef: React.MutableRefObject<boolean>;
  commitRef: React.MutableRefObject<(() => void) | null>;
  onCancel: () => void;
  isDisabled?: boolean;
  sx?: SxProps<Theme>;
  containerSx?: SxProps<Theme>;
}

const InlineEditActions: React.FC<InlineEditActionsProps> = ({
  preventCommitRef,
  commitRef,
  onCancel,
  isDisabled,
  sx,
  containerSx,
}) => (
  <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, ...containerSx }}>
    <Button
      size="small"
      variant="contained"
      disabled={isDisabled}
      onMouseDown={(e) => {
        e.stopPropagation();
        e.preventDefault();
        preventCommitRef.current = true;
      }}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        preventCommitRef.current = false;
        commitRef.current?.();
      }}
      sx={sx}
    >
      Save
    </Button>
    <Button
      size="small"
      disabled={isDisabled}
      onMouseDown={(e) => {
        e.stopPropagation();
        preventCommitRef.current = true;
      }}
      onClick={(e) => {
        e.stopPropagation();
        onCancel();
      }}
      sx={sx}
    >
      Cancel
    </Button>
  </Box>
);

export default InlineEditActions;
