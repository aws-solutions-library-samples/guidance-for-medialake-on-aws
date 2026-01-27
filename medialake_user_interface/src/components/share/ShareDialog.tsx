import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Card,
  CardActionArea,
  Radio,
  FormControlLabel,
  RadioGroup,
  Checkbox,
  FormGroup,
  IconButton,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  CircularProgress,
  Alert,
  Divider,
  Tooltip,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DeleteIcon from "@mui/icons-material/Delete";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { useSnackbar } from "notistack";
import { useTranslation } from "react-i18next";
import {
  useCreateShare,
  useAssetShares,
  useRevokeShare,
  CreateShareOptions,
} from "@/api/hooks/useShares";
import { logger } from "@/common/helpers/logger";

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
  assetId: string;
  assetName?: string;
}

const EXPIRATION_OPTIONS = [
  { labelKey: "shareDialog.expirationOptions.twentyFourHours", value: 86400 },
  { labelKey: "shareDialog.expirationOptions.sevenDays", value: 604800 },
  { labelKey: "shareDialog.expirationOptions.thirtyDays", value: 2592000 },
  { labelKey: "shareDialog.expirationOptions.never", value: null },
];

export const ShareDialog: React.FC<ShareDialogProps> = ({ open, onClose, assetId, assetName }) => {
  const { t } = useTranslation();
  const { enqueueSnackbar } = useSnackbar();
  const [representationType, setRepresentationType] = useState<"proxy" | "original">("proxy");
  const [expiresIn, setExpiresIn] = useState<number | null>(604800); // 7 days default
  const [allowMetadata, setAllowMetadata] = useState(true);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const { data: shares, isLoading: loadingShares } = useAssetShares(assetId, { enabled: open });
  const createShare = useCreateShare();
  const revokeShare = useRevokeShare();

  const handleCreateShare = async () => {
    const options: CreateShareOptions = {
      representationType,
      allowMetadata,
      expiresIn,
    };

    try {
      const result = await createShare.mutateAsync({ assetId, options });
      logger.info("Share created", result);
      // Show the share URL in a snackbar so user can quickly copy it
      if (result.shareUrl) {
        enqueueSnackbar(
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body2">{t("shareDialog.createShareLink")}!</Typography>
            <Button
              size="small"
              onClick={() => {
                navigator.clipboard.writeText(result.shareUrl);
                enqueueSnackbar(t("shareDialog.copyUrl"), { variant: "success" });
              }}
            >
              Copy URL
            </Button>
          </Box>,
          { variant: "success", autoHideDuration: 6000 }
        );
      }
      // Don't close dialog so user can see the new share
    } catch (error) {
      logger.error("Failed to create share", error);
    }
  };

  const handleCopyUrl = (shareUrl: string, shareToken: string) => {
    navigator.clipboard.writeText(shareUrl);
    setCopiedToken(shareToken);
    enqueueSnackbar(t("shareDialog.copyUrl"), { variant: "success" });
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const handleRevokeShare = async (shareToken: string) => {
    try {
      await revokeShare.mutateAsync({ assetId, shareToken });
    } catch (error) {
      logger.error("Failed to revoke share", error);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  const formatExpiration = (expiresAt?: number) => {
    if (!expiresAt) return t("shareDialog.expirationOptions.never");
    const now = Date.now() / 1000;
    if (expiresAt < now) return t("shareDialog.expired");
    const days = Math.floor((expiresAt - now) / 86400);
    if (days > 0) return `${days} day${days > 1 ? "s" : ""}`;
    const hours = Math.floor((expiresAt - now) / 3600);
    return `${hours} hour${hours > 1 ? "s" : ""}`;
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Typography variant="h6">{t("shareDialog.title")}</Typography>
        {assetName && (
          <Typography variant="body2" color="text.secondary">
            {assetName}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3, mt: 1 }}>
          {/* Representation Type Selection */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t("shareDialog.selectVersion")}
            </Typography>
            <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
              <Card
                variant="outlined"
                sx={{
                  flex: 1,
                  minWidth: 200,
                  border: representationType === "proxy" ? 2 : 1,
                  borderColor: representationType === "proxy" ? "primary.main" : "divider",
                }}
              >
                <CardActionArea
                  onClick={() => setRepresentationType("proxy")}
                  sx={{ p: 2, height: "100%" }}
                >
                  <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                    <Radio checked={representationType === "proxy"} />
                    <Box>
                      <Typography variant="subtitle1" fontWeight="medium">
                        {t("shareDialog.proxy")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.proxyDescription")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.proxyOptimized")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.proxyBandwidth")}
                      </Typography>
                      <Chip
                        label={t("shareDialog.recommended")}
                        size="small"
                        color="primary"
                        sx={{ mt: 1 }}
                      />
                    </Box>
                  </Box>
                </CardActionArea>
              </Card>

              <Card
                variant="outlined"
                sx={{
                  flex: 1,
                  minWidth: 200,
                  border: representationType === "original" ? 2 : 1,
                  borderColor: representationType === "original" ? "primary.main" : "divider",
                }}
              >
                <CardActionArea
                  onClick={() => setRepresentationType("original")}
                  sx={{ p: 2, height: "100%" }}
                >
                  <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                    <Radio checked={representationType === "original"} />
                    <Box>
                      <Typography variant="subtitle1" fontWeight="medium">
                        {t("shareDialog.original")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.originalQuality")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.originalResolution")}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        • {t("shareDialog.originalSize")}
                      </Typography>
                    </Box>
                  </Box>
                </CardActionArea>
              </Card>
            </Box>
          </Box>

          {/* Expiration Selection */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t("shareDialog.expiration")}
            </Typography>
            <RadioGroup
              row
              value={expiresIn === null ? "null" : expiresIn}
              onChange={(e) =>
                setExpiresIn(e.target.value === "null" ? null : parseInt(e.target.value))
              }
            >
              {EXPIRATION_OPTIONS.map((option) => (
                <FormControlLabel
                  key={option.labelKey}
                  value={option.value === null ? "null" : option.value}
                  control={<Radio />}
                  label={t(option.labelKey)}
                />
              ))}
            </RadioGroup>
          </Box>

          {/* Permissions */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              {t("shareDialog.permissions")}
            </Typography>
            <FormGroup>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={allowMetadata}
                    onChange={(e) => setAllowMetadata(e.target.checked)}
                  />
                }
                label={t("shareDialog.showMetadata")}
              />
            </FormGroup>
          </Box>

          {/* Existing Shares */}
          <Box>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>
              {t("shareDialog.existingShares")}
            </Typography>
            {loadingShares ? (
              <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
                <CircularProgress size={24} />
              </Box>
            ) : shares && shares.length > 0 ? (
              <List dense>
                {shares.map((share) => (
                  <ListItem
                    key={share.ShareToken}
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
                            color={
                              share.ShareSettings.representationType === "proxy"
                                ? "primary"
                                : "default"
                            }
                          />
                          <Chip
                            label={share.Status}
                            size="small"
                            color={share.Status === "active" ? "success" : "default"}
                          />
                        </Box>
                      }
                      secondary={
                        <Box sx={{ mt: 0.5 }}>
                          <Typography variant="caption" display="block">
                            {t("shareDialog.created")}: {formatDate(share.CreatedAt)}
                          </Typography>
                          <Typography variant="caption" display="block">
                            {t("shareDialog.expires")}: {formatExpiration(share.ExpiresAt)}
                          </Typography>
                          <Typography variant="caption" display="block">
                            {t("shareDialog.accessCount")}: {share.AccessCount}
                          </Typography>
                          <Typography variant="caption" display="block">
                            {t("shareDialog.downloadCount")}: {share.DownloadCount}
                          </Typography>
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
                          onClick={() => handleCopyUrl(share.ShareURL, share.ShareToken)}
                          sx={{ mr: 1 }}
                        >
                          {copiedToken === share.ShareToken ? (
                            <CheckCircleIcon color="success" />
                          ) : (
                            <ContentCopyIcon />
                          )}
                        </IconButton>
                      </Tooltip>
                      {share.Status === "active" && (
                        <Tooltip title={t("shareDialog.revokeShare")}>
                          <IconButton
                            edge="end"
                            onClick={() => handleRevokeShare(share.ShareToken)}
                            disabled={revokeShare.isPending}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Alert severity="info">{t("shareDialog.noShares")}</Alert>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("shareDialog.close")}</Button>
        <Button
          variant="contained"
          onClick={handleCreateShare}
          disabled={createShare.isPending}
          startIcon={createShare.isPending && <CircularProgress size={16} />}
        >
          {t("shareDialog.createShareLink")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
