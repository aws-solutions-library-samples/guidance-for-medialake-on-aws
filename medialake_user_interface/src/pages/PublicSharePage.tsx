import { useGenerateDownloadUrlMutation, usePublicShare } from "@/api/hooks/useShares";
import { useAwsConfig } from "@/common/hooks/aws-config-context";
import TechnicalMetadataTab from "@/components/TechnicalMetadataTab";
import PublicShareMediaViewer from "@/components/shared/PublicShareMediaViewer";
import { transformMetadata } from "@/utils/metadataUtils";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DownloadIcon from "@mui/icons-material/Download";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  IconButton,
  Paper,
  Tooltip,
  Typography,
} from "@mui/material";
import { useSnackbar } from "notistack";
import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

export const PublicSharePage: React.FC = () => {
  const { t } = useTranslation();
  const { token } = useParams<{ token: string }>();
  const awsConfig = useAwsConfig();
  const { enqueueSnackbar } = useSnackbar();

  const { data, isLoading, error } = usePublicShare(token!, {
    enabled: !!token,
  });

  const generateDownloadUrl = useGenerateDownloadUrlMutation();

  const assetType = data?.asset?.DigitalSourceAsset?.Type?.toLowerCase() ?? "";
  const fileName =
    data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey
      ?.Name ?? "Unknown";

  const origin = useMemo(() => {
    return typeof window !== "undefined" ? window.location.origin : "";
  }, []);

  /* Get direct link to asset */
  const assetLink = `${origin}/embed/${token}`;

  /* Transform metadata into TechnicalMetadataTab format */
  const metadataAccordions = useMemo(() => {
    if (!data?.asset?.Metadata) return [];
    return transformMetadata(data.asset.Metadata);
  }, [data?.asset?.Metadata]);

  const availableCategories = useMemo(() => {
    return metadataAccordions.map((acc) => acc.category);
  }, [metadataAccordions]);

  if (isLoading || !awsConfig) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "100vh",
          bgcolor: "background.default",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const handleDownload = () => {
    if (token) {
      generateDownloadUrl.mutate(token);
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(assetLink);
    enqueueSnackbar(t("publicShare.embed.linkCopied"), { variant: "success" });
  };

  if (error || !data) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            {(() => {
              if (typeof error === "object" && error !== null && "response" in error) {
                const message = (
                  (error as Record<string, unknown>).response as Record<
                    string,
                    Record<string, unknown>
                  >
                )?.data?.message;
                return message ? String(message) : t("publicShare.error.notFound");
              }
              return t("publicShare.error.notFound");
            })()}
          </Alert>
          <Typography variant="body1" color="text.secondary">
            {t("publicShare.error.notFoundMessage")}
          </Typography>
        </Paper>
      </Container>
    );
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        py: 4,
      }}
    >
      <Container maxWidth="lg">
        <Paper sx={{ overflow: "hidden" }}>
          {/* Header */}
          <Box sx={{ p: 3, bgcolor: "primary.main", color: "white" }}>
            <Typography variant="h5" gutterBottom>
              {t("publicShare.title")}
            </Typography>
            <Typography variant="body2">{fileName}</Typography>
            <Box sx={{ mt: 2, display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Chip
                label={`${assetType.toUpperCase()}`}
                size="small"
                sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}
              />
              <Chip
                label={`${
                  data?.shareInfo?.representationType === "proxy"
                    ? t("publicShare.representationType.webOptimized")
                    : t("publicShare.representationType.originalQuality")
                }`}
                size="small"
                sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}
              />
              {data?.shareInfo?.expiresAt && (
                <Chip
                  label={`${t("publicShare.expiry")}: ${new Date((data.shareInfo.expiresAt ?? 0) * 1000).toLocaleDateString()}`}
                  size="small"
                  sx={{ bgcolor: "rgba(255,255,255,0.2)", color: "white" }}
                />
              )}
            </Box>
          </Box>

          {/* Media Player */}
          <PublicShareMediaViewer
            viewUrl={data?.asset?.viewUrl}
            assetType={assetType}
            fileName={fileName}
            isLoading={isLoading}
          />

          {/* Actions and Metadata */}
          <Box sx={{ p: 3 }}>
            {data?.asset?.viewUrl && (
              <Box sx={{ mb: 3 }}>
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownload}
                  loading={generateDownloadUrl.isPending}
                  fullWidth
                >
                  {generateDownloadUrl.isPending
                    ? t("publicShare.generatingDownload")
                    : t("publicShare.downloadFile")}
                </Button>
              </Box>
            )}

            {/* Share Link Section */}
            {data?.shareInfo?.allowEmbedding && (
              <>
                <Divider sx={{ my: 3 }} />
                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      mb: 1,
                    }}
                  >
                    <Typography variant="h6">{t("publicShare.embed.title")}</Typography>
                    <Tooltip title={t("publicShare.embed.copyLink")}>
                      <IconButton size="small" onClick={handleCopyLink}>
                        <ContentCopyIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {t("publicShare.embed.description")}
                  </Typography>
                  <Paper
                    sx={{
                      p: 2,
                      bgcolor: "background.paper",
                      border: "1px solid",
                      borderColor: "divider",
                      borderRadius: 1,
                      overflow: "auto",
                      boxShadow: 1,
                    }}
                  >
                    <Typography
                      component="pre"
                      sx={{
                        fontFamily: "monospace",
                        fontSize: "0.875rem",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        color: "text.primary",
                        m: 0,
                      }}
                    >
                      {assetLink}
                    </Typography>
                  </Paper>
                </Box>
              </>
            )}

            {/* Metadata Section */}
            {data?.asset?.Metadata && metadataAccordions.length > 0 && (
              <>
                <Divider sx={{ my: 3 }} />
                <Typography variant="h6" gutterBottom>
                  {t("publicShare.assetMetadata")}
                </Typography>
                <Box sx={{ mt: 2 }}>
                  <TechnicalMetadataTab
                    metadataAccordions={metadataAccordions}
                    availableCategories={availableCategories}
                    mediaType={assetType as "image" | "audio" | "video"}
                  />
                </Box>
              </>
            )}
          </Box>

          {/* Footer */}
          <Box
            sx={{
              p: 2,
              bgcolor: "background.paper",
              borderTop: 1,
              borderColor: "divider",
              textAlign: "center",
            }}
          >
            <Typography variant="caption" color="text.secondary">
              {t("publicShare.poweredBy")}
            </Typography>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
};
