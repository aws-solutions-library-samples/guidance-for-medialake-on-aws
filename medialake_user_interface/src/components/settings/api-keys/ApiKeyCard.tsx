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
} from "@mui/material";
import {
  Visibility as VisibilityIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from "@mui/icons-material";
import { formatDistanceToNow } from "date-fns";
import { Can } from "@/permissions/components/Can";
import { ApiKey } from "@/api/types/apiKey.types";
import { useTranslation } from "react-i18next";

interface ApiKeyCardProps {
  apiKey: ApiKey;
  onView: (apiKey: ApiKey) => void;
  onEdit: (apiKey: ApiKey) => void;
  onDelete: (apiKey: ApiKey) => void;
}

const ApiKeyCard: React.FC<ApiKeyCardProps> = ({ apiKey, onView, onEdit, onDelete }) => {
  const { t } = useTranslation();
  const formatDate = (dateString: string) => {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true });
  };

  return (
    <Card
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        transition: "all 0.2s ease-in-out",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: (theme) => theme.shadows[4],
        },
        opacity: apiKey.isEnabled ? 1 : 0.7,
      }}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        {/* Header with name and status */}
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
          <Typography
            variant="h6"
            component="h3"
            sx={{
              fontWeight: 600,
              fontSize: "1rem",
              lineHeight: 1.2,
              mr: 1,
            }}
          >
            {apiKey.name}
          </Typography>
          <Chip
            label={apiKey.isEnabled ? t("common.labels.enabled") : t("common.labels.disabled")}
            size="small"
            color={apiKey.isEnabled ? "success" : "default"}
            sx={{
              fontWeight: 500,
              minWidth: 70,
            }}
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
              lineHeight: 1.25,
            }}
          >
            {apiKey.description}
          </Typography>
        )}

        {/* Metadata */}
        <Box sx={{ mt: "auto" }}>
          <Typography variant="caption" color="text.secondary" display="block">
            Created {formatDate(apiKey.createdAt)}
          </Typography>
          {apiKey.updatedAt !== apiKey.createdAt && (
            <Typography variant="caption" color="text.secondary" display="block">
              Updated {formatDate(apiKey.updatedAt)}
            </Typography>
          )}
          {apiKey.lastUsed && (
            <Typography variant="caption" color="text.secondary" display="block">
              Last used {formatDate(apiKey.lastUsed)}
            </Typography>
          )}
        </Box>
      </CardContent>

      <CardActions
        sx={{
          justifyContent: "flex-end",
          px: 2,
          pb: 2,
          pt: 0,
        }}
      >
        {/* View Button */}
        <Can I="view" a="api-key">
          <Tooltip title={t("common.actions.viewDetails")}>
            <IconButton
              size="small"
              onClick={() => onView(apiKey)}
              sx={{
                color: "primary.main",
                "&:hover": {
                  backgroundColor: "primary.main",
                  color: "primary.contrastText",
                },
              }}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Can>

        {/* Edit Button */}
        <Can I="edit" a="api-key">
          <Tooltip title={t("common.editApiKey")}>
            <IconButton
              size="small"
              onClick={() => onEdit(apiKey)}
              sx={{
                color: "info.main",
                "&:hover": {
                  backgroundColor: "info.main",
                  color: "info.contrastText",
                },
              }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Can>

        {/* Delete Button */}
        <Can I="delete" a="api-key">
          <Tooltip title={t("common.deleteApiKey")}>
            <IconButton
              size="small"
              onClick={() => onDelete(apiKey)}
              sx={{
                color: "error.main",
                "&:hover": {
                  backgroundColor: "error.main",
                  color: "error.contrastText",
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
