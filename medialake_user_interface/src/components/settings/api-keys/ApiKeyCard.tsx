import React from "react";
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  IconButton,
  Box,
  Tooltip,
  alpha,
} from "@mui/material";
import {
  Visibility as VisibilityIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  AccessTime as AccessTimeIcon,
  VpnKey as VpnKeyIcon,
} from "@mui/icons-material";
import { Can } from "@/permissions/components/Can";
import { ApiKey } from "@/api/types/apiKey.types";
import { useTranslation } from "react-i18next";
import { formatRelativeTime, formatLocalDateTime } from "@/shared/utils/dateUtils";

interface ApiKeyCardProps {
  apiKey: ApiKey;
  onView: (apiKey: ApiKey) => void;
  onEdit: (apiKey: ApiKey) => void;
  onDelete: (apiKey: ApiKey) => void;
}

const ApiKeyCard: React.FC<ApiKeyCardProps> = ({ apiKey, onView, onEdit, onDelete }) => {
  const { t } = useTranslation();

  return (
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        transition: "all 0.2s ease-in-out",
        border: (theme) =>
          `1px solid ${
            apiKey.isEnabled
              ? alpha(theme.palette.divider, 0.12)
              : alpha(theme.palette.divider, 0.08)
          }`,
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: (theme) => theme.shadows[6],
          borderColor: (theme) => alpha(theme.palette.primary.main, 0.3),
        },
        opacity: apiKey.isEnabled ? 1 : 0.65,
        cursor: "pointer",
      }}
      onClick={() => onView(apiKey)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onView(apiKey);
        }
      }}
      aria-label={`${apiKey.name} API key, ${apiKey.isEnabled ? "enabled" : "disabled"}`}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        {/* Header row */}
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1.5}>
          <Box sx={{ mr: 1, minWidth: 0, flex: 1 }}>
            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
              <VpnKeyIcon
                sx={{
                  fontSize: 18,
                  color: apiKey.isEnabled ? "primary.main" : "text.disabled",
                  flexShrink: 0,
                }}
              />
              <Typography
                variant="subtitle1"
                component="h3"
                sx={{
                  fontWeight: 600,
                  lineHeight: 1.3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {apiKey.name}
              </Typography>
            </Box>
            {apiKey.scope && apiKey.scope !== "custom" && (
              <Chip
                label={apiKey.scope}
                size="small"
                variant="outlined"
                color="info"
                sx={{
                  ml: 3.5,
                  textTransform: "capitalize",
                  height: 20,
                  fontSize: "0.7rem",
                }}
              />
            )}
          </Box>
          <Chip
            label={apiKey.isEnabled ? t("common.labels.enabled") : t("common.labels.disabled")}
            size="small"
            color={apiKey.isEnabled ? "success" : "default"}
            sx={{ fontWeight: 500, minWidth: 70, flexShrink: 0 }}
          />
        </Box>

        {/* Description */}
        {apiKey.description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mb: 2,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              minHeight: "2.5em",
              lineHeight: 1.4,
            }}
          >
            {apiKey.description}
          </Typography>
        )}

        {/* Timestamps */}
        <Box
          sx={{
            mt: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 0.25,
          }}
        >
          <Tooltip title={formatLocalDateTime(apiKey.createdAt)} placement="top-start" arrow>
            <Box display="flex" alignItems="center" gap={0.5}>
              <AccessTimeIcon sx={{ fontSize: 13, color: "text.disabled" }} />
              <Typography variant="caption" color="text.secondary">
                {t("apiKeys.card.created", "Created")} {formatRelativeTime(apiKey.createdAt)}
              </Typography>
            </Box>
          </Tooltip>

          {apiKey.updatedAt !== apiKey.createdAt && (
            <Tooltip title={formatLocalDateTime(apiKey.updatedAt)} placement="top-start" arrow>
              <Box display="flex" alignItems="center" gap={0.5}>
                <AccessTimeIcon sx={{ fontSize: 13, color: "text.disabled" }} />
                <Typography variant="caption" color="text.secondary">
                  {t("apiKeys.card.updated", "Updated")} {formatRelativeTime(apiKey.updatedAt)}
                </Typography>
              </Box>
            </Tooltip>
          )}

          {apiKey.lastUsed && (
            <Tooltip title={formatLocalDateTime(apiKey.lastUsed)} placement="top-start" arrow>
              <Box display="flex" alignItems="center" gap={0.5}>
                <AccessTimeIcon sx={{ fontSize: 13, color: "text.disabled" }} />
                <Typography variant="caption" color="text.secondary">
                  {t("apiKeys.card.lastUsed", "Last used")} {formatRelativeTime(apiKey.lastUsed)}
                </Typography>
              </Box>
            </Tooltip>
          )}
        </Box>
      </CardContent>

      <CardActions
        sx={{
          justifyContent: "flex-end",
          px: 2,
          pb: 1.5,
          pt: 0,
          borderTop: (theme) => `1px solid ${alpha(theme.palette.divider, 0.06)}`,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Can I="view" a="api-key">
          <Tooltip title={t("common.actions.viewDetails")}>
            <IconButton
              size="small"
              onClick={() => onView(apiKey)}
              aria-label={t("common.actions.viewDetails")}
              sx={{
                color: "primary.main",
                "&:hover": {
                  backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.08),
                },
              }}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Can>

        <Can I="edit" a="api-key">
          <Tooltip title={t("common.editApiKey")}>
            <IconButton
              size="small"
              onClick={() => onEdit(apiKey)}
              aria-label={t("common.editApiKey")}
              sx={{
                color: "info.main",
                "&:hover": {
                  backgroundColor: (theme) => alpha(theme.palette.info.main, 0.08),
                },
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Can>

        <Can I="delete" a="api-key">
          <Tooltip title={t("common.deleteApiKey")}>
            <IconButton
              size="small"
              onClick={() => onDelete(apiKey)}
              aria-label={t("common.deleteApiKey")}
              sx={{
                color: "error.main",
                "&:hover": {
                  backgroundColor: (theme) => alpha(theme.palette.error.main, 0.08),
                },
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Can>
      </CardActions>
    </Card>
  );
};

export default ApiKeyCard;
