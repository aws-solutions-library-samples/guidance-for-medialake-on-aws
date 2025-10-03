import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
  IconButton,
  Chip,
  Divider,
  TextField,
  InputAdornment,
  Tooltip,
} from "@mui/material";
import {
  Close as CloseIcon,
  Edit as EditIcon,
  ContentCopy as CopyIcon,
} from "@mui/icons-material";
import { format } from "date-fns";
import { ActionButton } from "@/components/common/button/ActionButton";
import { Can } from "@/permissions/components/Can";
import { useGetApiKey } from "@/api/hooks/useApiKeys";
import { ApiKey } from "@/api/types/apiKey.types";

interface ApiKeyDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  onEdit: (apiKey: ApiKey) => void;
  apiKey: ApiKey | null;
}

const ApiKeyDetailsDialog: React.FC<ApiKeyDetailsDialogProps> = ({
  open,
  onClose,
  onEdit,
  apiKey,
}) => {
  const [copySuccess, setCopySuccess] = useState(false);

  // Fetch detailed API key information when dialog opens
  const {
    data: detailedApiKey,
    isLoading,
    error,
  } = useGetApiKey(apiKey?.id || "", open && !!apiKey);

  // Use detailed data if available, otherwise fall back to provided apiKey
  const displayApiKey = detailedApiKey || apiKey;

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), "PPpp");
  };

  const handleCopyId = async () => {
    if (displayApiKey?.id) {
      try {
        await navigator.clipboard.writeText(displayApiKey.id);
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      } catch (error) {
        console.error("Failed to copy to clipboard:", error);
      }
    }
  };

  const handleEdit = () => {
    if (displayApiKey) {
      onEdit(displayApiKey);
    }
  };

  if (!displayApiKey) {
    return null;
  }

  // Mask the API key ID for display (show first 8 and last 4 characters)
  const maskApiKeyId = (id: string) => {
    if (id.length <= 12) return id;
    return `${id.slice(0, 8)}${"•".repeat(Math.max(0, id.length - 12))}${id.slice(-4)}`;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          minHeight: "500px",
        },
      }}
    >
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">API Key Details</Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {isLoading && (
          <Box display="flex" justifyContent="center" py={4}>
            <Typography>Loading API key details...</Typography>
          </Box>
        )}

        {error && (
          <Box py={2}>
            <Typography color="error">
              Failed to load API key details. Please try again.
            </Typography>
          </Box>
        )}

        {displayApiKey && !isLoading && (
          <Box>
            {/* Name and Status */}
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              mb={2}
            >
              <Typography variant="h6" component="h2">
                {displayApiKey.name}
              </Typography>
              <Chip
                label={displayApiKey.isEnabled ? "Enabled" : "Disabled"}
                color={displayApiKey.isEnabled ? "success" : "default"}
                size="small"
              />
            </Box>

            {/* Description */}
            {displayApiKey.description && (
              <>
                <Typography variant="subtitle2" gutterBottom>
                  Description
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {displayApiKey.description}
                </Typography>
              </>
            )}

            <Divider sx={{ my: 2 }} />

            {/* API Key ID */}
            <Typography variant="subtitle2" gutterBottom>
              API Key ID
            </Typography>
            <TextField
              fullWidth
              value={maskApiKeyId(displayApiKey.id)}
              InputProps={{
                readOnly: true,
                endAdornment: (
                  <InputAdornment position="end">
                    <Tooltip
                      title={copySuccess ? "Copied!" : "Copy API Key ID"}
                    >
                      <IconButton
                        onClick={handleCopyId}
                        size="small"
                        color={copySuccess ? "success" : "default"}
                      >
                        <CopyIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </InputAdornment>
                ),
                sx: {
                  fontFamily: "monospace",
                  fontSize: "0.875rem",
                },
              }}
              sx={{ mb: 2 }}
            />

            <Divider sx={{ my: 2 }} />

            {/* Metadata */}
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Created
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {formatDate(displayApiKey.createdAt)}
              </Typography>

              <Typography variant="subtitle2" gutterBottom>
                Last Updated
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {formatDate(displayApiKey.updatedAt)}
              </Typography>

              {displayApiKey.lastUsed && (
                <>
                  <Typography variant="subtitle2" gutterBottom>
                    Last Used
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    {formatDate(displayApiKey.lastUsed)}
                  </Typography>
                </>
              )}
            </Box>
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <ActionButton variant="text" onClick={onClose}>
          Close
        </ActionButton>
        <Can I="edit" a="api-key">
          <ActionButton
            variant="contained"
            startIcon={<EditIcon />}
            onClick={handleEdit}
            disabled={isLoading || !displayApiKey}
          >
            Edit
          </ActionButton>
        </Can>
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyDetailsDialog;
