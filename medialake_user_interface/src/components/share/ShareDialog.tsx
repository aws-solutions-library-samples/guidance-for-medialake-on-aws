import {
  CreateShareOptions,
  useAssetShares,
  useCreateShare,
  useRevokeShare,
} from "@/api/hooks/useShares";
import { logger } from "@/common/helpers/logger";
import { Can } from "@/permissions/components/Can";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  FormGroup,
  List,
  Radio,
  RadioGroup,
  Typography,
} from "@mui/material";
import { useSnackbar } from "notistack";
import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { ShareItem } from "./ShareItem";

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
  const [allowEmbedding, setallowEmbedding] = useState(true);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const { data: shares, isLoading: loadingShares } = useAssetShares(assetId, { enabled: open });
  const createShare = useCreateShare();
  const revokeShare = useRevokeShare();

  const handleCreateShare = async () => {
    const options: CreateShareOptions = {
      representationType,
      allowMetadata,
      allowEmbedding,
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
          <Can I="externalShare" a="asset">
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
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={allowEmbedding}
                      onChange={(e) => setallowEmbedding(e.target.checked)}
                    />
                  }
                  label={t("shareDialog.allowEmbedding")}
                />
              </FormGroup>
            </Box>
            <Divider sx={{ my: 2 }} />
          </Can>

          {/* Existing Shares */}
          <Box>
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
                  <ShareItem
                    key={share.ShareToken}
                    share={share}
                    copiedToken={copiedToken}
                    revokeSharePending={revokeShare.isPending}
                    onCopyUrl={handleCopyUrl}
                    onRevokeShare={handleRevokeShare}
                    formatDate={formatDate}
                  />
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
