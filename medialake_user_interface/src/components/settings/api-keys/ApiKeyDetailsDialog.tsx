import React, { useState } from "react";
import { useTranslation } from "react-i18next";
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
  alpha,
  CircularProgress,
} from "@mui/material";
import {
  Close as CloseIcon,
  Edit as EditIcon,
  ContentCopy as CopyIcon,
  AccessTime as AccessTimeIcon,
  VpnKey as VpnKeyIcon,
  Shield as ShieldIcon,
} from "@mui/icons-material";
import { ActionButton } from "@/components/common/button/ActionButton";
import { Can } from "@/permissions/components/Can";
import { useGetApiKey } from "@/api/hooks/useApiKeys";
import { ApiKey } from "@/api/types/apiKey.types";
import { formatLocalDateTime, formatRelativeTime } from "@/shared/utils/dateUtils";

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
  const { t } = useTranslation();
  const [copySuccess, setCopySuccess] = useState(false);

  // Fetch detailed API key information when dialog opens
  const {
    data: detailedApiKey,
    isLoading,
    error,
  } = useGetApiKey(apiKey?.id || "", open && !!apiKey);

  // Use detailed data if available, otherwise fall back to provided apiKey
  const displayApiKey = detailedApiKey || apiKey;

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

  const scopeColor = (scope?: string) => {
    switch (scope) {
      case "admin":
        return "error";
      case "read-write":
        return "primary";
      case "read-only":
        return "default";
      default:
        return "info";
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 },
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box display="flex" alignItems="center" gap={1}>
            <VpnKeyIcon sx={{ color: "primary.main", fontSize: 22 }} />
            <Typography variant="h6">{t("apiKeys.dialogs.detailsTitle")}</Typography>
          </Box>
          <IconButton onClick={onClose} size="small" aria-label={t("common.dialogs.close")}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        {isLoading && (
          <Box display="flex" justifyContent="center" alignItems="center" py={6}>
            <CircularProgress size={32} />
          </Box>
        )}

        {error && (
          <Box py={2}>
            <Typography color="error">{t("apiKeys.errors.loadFailed")}</Typography>
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
              sx={{
                p: 1.5,
                borderRadius: 1.5,
                backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.04),
              }}
            >
              <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
                {displayApiKey.name}
              </Typography>
              <Chip
                label={
                  displayApiKey.isEnabled ? t("common.status.enabled") : t("common.status.disabled")
                }
                color={displayApiKey.isEnabled ? "success" : "default"}
                size="small"
                sx={{ fontWeight: 500 }}
              />
            </Box>

            {/* Description */}
            {displayApiKey.description && (
              <Box mb={2}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}
                >
                  {t("apiKeys.details.description")}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {displayApiKey.description}
                </Typography>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            {/* API Key ID */}
            <Box mb={2}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}
              >
                {t("apiKeys.details.apiKeyId")}
              </Typography>
              <TextField
                fullWidth
                size="small"
                value={maskApiKeyId(displayApiKey.id)}
                InputProps={{
                  readOnly: true,
                  endAdornment: (
                    <InputAdornment position="end">
                      <Tooltip
                        title={
                          copySuccess
                            ? t("common.actions.copied")
                            : t("apiKeys.tooltips.copyApiKeyId")
                        }
                      >
                        <IconButton
                          onClick={handleCopyId}
                          size="small"
                          color={copySuccess ? "success" : "default"}
                          aria-label={t("apiKeys.tooltips.copyApiKeyId")}
                        >
                          <CopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </InputAdornment>
                  ),
                  sx: {
                    fontFamily: "monospace",
                    fontSize: "0.85rem",
                  },
                }}
                sx={{ mt: 0.5 }}
              />
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Scope & Permissions */}
            {displayApiKey.scope && (
              <Box mb={2}>
                <Box display="flex" alignItems="center" gap={0.5} mb={0.5}>
                  <ShieldIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}
                  >
                    {t("apiKeys.details.scope")}
                  </Typography>
                </Box>
                <Chip
                  label={displayApiKey.scope}
                  size="small"
                  color={scopeColor(displayApiKey.scope)}
                  sx={{ textTransform: "capitalize" }}
                />
              </Box>
            )}

            {displayApiKey.permissions && Object.keys(displayApiKey.permissions).length > 0 && (
              <Box mb={2}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                    fontWeight: 600,
                    display: "block",
                    mb: 0.5,
                  }}
                >
                  {t("apiKeys.details.permissions")}
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                  {Object.entries(displayApiKey.permissions)
                    .filter(([, v]) => v === true)
                    .map(([perm]) => (
                      <Chip key={perm} label={perm} size="small" variant="outlined" />
                    ))}
                </Box>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            {/* Timestamps */}
            <Box>
              <Box display="flex" alignItems="center" gap={0.5} mb={1.5}>
                <AccessTimeIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}
                >
                  {t("apiKeys.details.timeline", "Timeline")}
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: 1,
                  alignItems: "baseline",
                }}
              >
                <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                  {t("apiKeys.details.created")}
                </Typography>
                <Tooltip title={formatRelativeTime(displayApiKey.createdAt)} arrow>
                  <Typography variant="body2">
                    {formatLocalDateTime(displayApiKey.createdAt)}
                  </Typography>
                </Tooltip>

                <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                  {t("apiKeys.details.lastUpdated")}
                </Typography>
                <Tooltip title={formatRelativeTime(displayApiKey.updatedAt)} arrow>
                  <Typography variant="body2">
                    {formatLocalDateTime(displayApiKey.updatedAt)}
                  </Typography>
                </Tooltip>

                {displayApiKey.lastUsed && (
                  <>
                    <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                      {t("apiKeys.details.lastUsed")}
                    </Typography>
                    <Tooltip title={formatRelativeTime(displayApiKey.lastUsed)} arrow>
                      <Typography variant="body2">
                        {formatLocalDateTime(displayApiKey.lastUsed)}
                      </Typography>
                    </Tooltip>
                  </>
                )}
              </Box>
            </Box>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <ActionButton variant="text" onClick={onClose}>
          {t("common.dialogs.close")}
        </ActionButton>
        <Can I="edit" a="api-key">
          <ActionButton
            variant="contained"
            startIcon={<EditIcon />}
            onClick={handleEdit}
            disabled={isLoading || !displayApiKey}
          >
            {t("common.actions.edit")}
          </ActionButton>
        </Can>
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyDetailsDialog;
