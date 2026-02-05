import { Share } from "@/api/hooks/useShares";
import { Can } from "@/permissions/components/Can";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DeleteIcon from "@mui/icons-material/Delete";
import {
  Box,
  Chip,
  IconButton,
  ListItem,
  ListItemSecondaryAction,
  ListItemText,
  Tooltip,
  Typography,
} from "@mui/material";
import React from "react";
import { useTranslation } from "react-i18next";

interface ShareItemProps {
  share: Share;
  copiedToken: string | null;
  revokeSharePending: boolean;
  onCopyUrl: (shareUrl: string, shareToken: string) => void;
  onRevokeShare: (shareToken: string) => void;
  formatDate: (timestamp: number) => string;
}

export const ShareItem: React.FC<ShareItemProps> = ({
  share,
  copiedToken,
  revokeSharePending,
  onCopyUrl,
  onRevokeShare,
  formatDate,
}) => {
  const { t } = useTranslation();

  const permissionsText = [
    share.ShareSettings.allowMetadata && t("shareDialog.showMetadata"),
    share.ShareSettings.allowEmbedding && t("shareDialog.allowEmbedding"),
  ]
    .filter(Boolean)
    .join(", ");

  // Check if share is expired
  const isExpired = share.ExpiresAt && share.ExpiresAt < Date.now() / 1000;
  const displayStatus = isExpired ? "expired" : share.Status;
  const statusColor = isExpired ? "error" : share.Status === "active" ? "success" : "default";
  const canRevoke = !isExpired && share.Status === "active" && share.IsOwner;

  return (
    <ListItem
      sx={{
        border: 1,
        borderColor: "divider",
        borderRadius: 1,
        mb: 1,
      }}
    >
      <ListItemText
        primary={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Chip
              label={share.ShareSettings.representationType}
              size="small"
              color={share.ShareSettings.representationType === "proxy" ? "primary" : "default"}
            />
            <Chip label={displayStatus} size="small" color={statusColor} />
          </Box>
        }
        secondary={
          <Box sx={{ mt: 0.5 }}>
            <Typography variant="caption" display="block">
              {t("shareDialog.created")}: {formatDate(share.CreatedAt)}
            </Typography>
            <Typography variant="caption" display="block">
              {t("shareDialog.expires")}:{" "}
              {share.ExpiresAt
                ? formatDate(share.ExpiresAt)
                : t("shareDialog.expirationOptions.never")}
            </Typography>
            <Typography variant="caption" display="block">
              {t("shareDialog.accessCount")}: {share.AccessCount}
            </Typography>
            <Typography variant="caption" display="block">
              {t("shareDialog.downloadCount")}: {share.DownloadCount}
            </Typography>
            {permissionsText && (
              <Typography variant="caption" display="block">
                {t("shareDialog.permissions")}: {permissionsText}
              </Typography>
            )}
            <Typography
              component="a"
              href={share.ShareURL}
              target="_blank"
              rel="noopener noreferrer"
              variant="caption"
              sx={{
                display: "block",
                wordBreak: "break-all",
                color: "primary.main",
                mt: 0.5,
                cursor: "pointer",
                textDecoration: "none",
                "&:hover": {
                  textDecoration: "underline",
                },
              }}
            >
              {share.ShareURL}
            </Typography>
          </Box>
        }
      />
      <ListItemSecondaryAction>
        <Tooltip title={t("shareDialog.copyUrl")}>
          <IconButton
            edge="end"
            onClick={() => onCopyUrl(share.ShareURL, share.ShareToken)}
            sx={{ mr: 1 }}
          >
            {copiedToken === share.ShareToken ? (
              <CheckCircleIcon color="success" />
            ) : (
              <ContentCopyIcon />
            )}
          </IconButton>
        </Tooltip>
        <Can I="externalShare" a="asset">
          {canRevoke && (
            <Tooltip title={t("shareDialog.revokeShare")}>
              <IconButton
                edge="end"
                onClick={() => onRevokeShare(share.ShareToken)}
                disabled={revokeSharePending}
              >
                <DeleteIcon />
              </IconButton>
            </Tooltip>
          )}
        </Can>
      </ListItemSecondaryAction>
    </ListItem>
  );
};
