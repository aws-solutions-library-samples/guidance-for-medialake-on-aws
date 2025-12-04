import React, { useEffect } from "react";
import {
  Dialog,
  DialogContent,
  Typography,
  CircularProgress,
  Box,
  useTheme,
  IconButton,
  Button,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";
import CancelIcon from "@mui/icons-material/Cancel";

interface ApiStatusModalProps {
  open: boolean;
  onClose?: () => void;
  status: "loading" | "success" | "error";
  action: string;
  message?: string;
  progress?: number;
  jobId?: string;
  onCancel?: () => void;
  cancelDisabled?: boolean;
  cancelLabel?: string;
}

const ApiStatusModal: React.FC<ApiStatusModalProps> = ({
  open,
  onClose,
  status,
  action,
  message,
  progress,
  jobId,
  onCancel,
  cancelDisabled = false,
  cancelLabel = "Cancel",
}) => {
  const theme = useTheme();

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    // Only auto-close on success if there's no job ID (not a tracked job)
    if (open && status === "success" && onClose && !jobId) {
      timeoutId = setTimeout(() => {
        onClose();
      }, 3000);
    }
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [open, status, onClose, jobId]);

  const getStatusContent = () => {
    switch (status) {
      case "loading":
        return (
          <>
            <Box sx={{ position: "relative", display: "inline-flex", mb: 3 }}>
              {progress !== undefined ? (
                <>
                  <CircularProgress
                    variant="determinate"
                    value={100}
                    size={100}
                    thickness={4}
                    sx={{
                      color: theme.palette.action.disabledBackground,
                      position: "absolute",
                    }}
                  />
                  <CircularProgress
                    variant="determinate"
                    value={progress}
                    size={100}
                    thickness={4}
                    sx={{ color: theme.palette.primary.main }}
                  />
                  <Box
                    sx={{
                      top: 0,
                      left: 0,
                      bottom: 0,
                      right: 0,
                      position: "absolute",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Typography
                      variant="h5"
                      component="div"
                      sx={{
                        color: theme.palette.primary.main,
                        fontWeight: 600,
                      }}
                    >
                      {`${Math.round(progress)}%`}
                    </Typography>
                  </Box>
                </>
              ) : (
                <CircularProgress
                  variant="indeterminate"
                  size={100}
                  thickness={4}
                  sx={{ color: theme.palette.primary.main }}
                />
              )}
            </Box>
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
            {message && (
              <Typography variant="body2" sx={{ mt: 1, color: theme.palette.text.secondary }}>
                {message}
              </Typography>
            )}
            {onCancel && (
              <Button
                variant="outlined"
                color="error"
                startIcon={<CancelIcon />}
                onClick={onCancel}
                disabled={cancelDisabled}
                sx={{ mt: 2 }}
                data-testid="cancel-operation-button"
              >
                {cancelLabel}
              </Button>
            )}
          </>
        );
      case "success":
        return (
          <>
            <CheckCircleIcon sx={{ fontSize: 48, mb: 2, color: theme.palette.success.main }} />
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
            {message && (
              <Typography variant="body1" sx={{ mt: 1, color: theme.palette.text.secondary }}>
                {message}
              </Typography>
            )}
          </>
        );
      case "error":
        return (
          <>
            <ErrorIcon sx={{ fontSize: 48, mb: 2, color: theme.palette.error.main }} />
            <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
              {action}
            </Typography>
            {message && (
              <Typography variant="body1" sx={{ mt: 1, color: theme.palette.error.main }}>
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
