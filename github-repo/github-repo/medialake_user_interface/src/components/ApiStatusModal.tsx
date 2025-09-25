import React, { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  Typography,
  CircularProgress,
  Box,
  useTheme,
  IconButton,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";

interface ApiStatusModalProps {
  open: boolean;
  onClose?: () => void;
  status: "loading" | "success" | "error";
  action: string;
  message?: string;
}

const ApiStatusModal: React.FC<ApiStatusModalProps> = ({
  open,
  onClose,
  status,
  action,
  message,
}) => {
  const theme = useTheme();

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    if (open && status === "success" && onClose) {
      timeoutId = setTimeout(() => {
        onClose();
      }, 3000);
    }
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [open, status, onClose]);

  const getStatusContent = () => {
    switch (status) {
      case "loading":
        return (
          <>
            <CircularProgress
              size={48}
              sx={{ mb: 2, color: theme.palette.primary.main }}
            />
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
          </>
        );
      case "success":
        return (
          <>
            <CheckCircleIcon
              sx={{ fontSize: 48, mb: 2, color: theme.palette.success.main }}
            />
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
            {message && (
              <Typography
                variant="body1"
                sx={{ mt: 1, color: theme.palette.text.secondary }}
              >
                {message}
              </Typography>
            )}
          </>
        );
      case "error":
        return (
          <>
            <ErrorIcon
              sx={{ fontSize: 48, mb: 2, color: theme.palette.error.main }}
            />
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
            {message && (
              <Typography
                variant="body1"
                sx={{ mt: 1, color: theme.palette.error.main }}
              >
                {message}
              </Typography>
            )}
          </>
        );
    }
  };

  return (
    <Dialog
      open={open}
      onClose={status === "loading" ? undefined : onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          p: 2,
        },
      }}
    >
      {status !== "loading" && onClose && (
        <IconButton
          onClick={onClose}
          sx={{
            position: "absolute",
            right: 8,
            top: 8,
            color: theme.palette.grey[500],
          }}
        >
          <CloseIcon />
        </IconButton>
      )}
      <DialogContent>
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            py: 2,
          }}
        >
          {getStatusContent()}
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default ApiStatusModal;
