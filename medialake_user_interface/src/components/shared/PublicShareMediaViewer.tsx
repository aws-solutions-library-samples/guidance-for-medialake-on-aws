import React, { useRef, useMemo } from "react";
import { Box, Alert, CircularProgress, Paper } from "@mui/material";
import { useTranslation } from "react-i18next";
import AssetVideo from "../asset/AssetVideo";
import ImageViewer from "../common/ImageViewer";
import { VideoViewerRef } from "../common/VideoViewer";

interface PublicShareMediaViewerProps {
  viewUrl?: string;
  assetType: string;
  fileName: string;
  isLoading?: boolean;
}

/**
 * PublicShareMediaViewer - Unified component for displaying video, audio, and image assets
 * in the public share page, using the same components as the detail pages.
 */
export const PublicShareMediaViewer: React.FC<PublicShareMediaViewerProps> = ({
  viewUrl,
  assetType,
  fileName,
  isLoading = false,
}) => {
  const { t } = useTranslation();
  const videoViewerRef = useRef<VideoViewerRef>(null);

  const normalizedType = useMemo(() => {
    return assetType.toLowerCase();
  }, [assetType]);

  // Show loading state
  if (isLoading) {
    return (
      <Box sx={{ px: 3, py: 3, height: "75vh", minHeight: "600px" }}>
        <Paper
          elevation={0}
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            background: "transparent",
            position: "relative",
            height: "100%",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <CircularProgress />
        </Paper>
      </Box>
    );
  }

  // Show error if no viewUrl
  if (!viewUrl) {
    return (
      <Box sx={{ px: 3, py: 3, height: "75vh", minHeight: "600px" }}>
        <Paper
          elevation={0}
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            background: "transparent",
            position: "relative",
            height: "100%",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            p: 2,
          }}
        >
          <Alert severity="warning">{t("publicShare.media.previewNotAvailable")}</Alert>
        </Paper>
      </Box>
    );
  }

  // Video asset
  if (normalizedType === "video") {
    return (
      <Box sx={{ px: 3, py: 3, height: "75vh", minHeight: "600px" }}>
        <Paper
          elevation={0}
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            background: "transparent",
            position: "relative",
            height: "100%",
            width: "100%",
          }}
        >
          <AssetVideo ref={videoViewerRef} src={viewUrl} protocol="video" />
        </Paper>
      </Box>
    );
  }

  // Audio asset
  if (normalizedType === "audio") {
    return (
      <Box sx={{ px: 3, py: 3, height: "75vh", minHeight: "600px" }}>
        <Paper
          elevation={0}
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            background: "transparent",
            position: "relative",
            height: "100%",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <AssetVideo ref={videoViewerRef} src={viewUrl} protocol="audio" />
        </Paper>
      </Box>
    );
  }

  // Image asset
  if (normalizedType === "image") {
    return (
      <Box sx={{ px: 3, py: 3, minHeight: "60vh" }}>
        <Box
          sx={{
            overflow: "hidden",
            borderRadius: 2,
            position: "relative",
          }}
        >
          <ImageViewer imageSrc={viewUrl} maxHeight={600} filename={fileName} />
        </Box>
      </Box>
    );
  }

  // Unsupported type
  return (
    <Box sx={{ px: 3, py: 3, height: "75vh", minHeight: "600px" }}>
      <Paper
        elevation={0}
        sx={{
          overflow: "hidden",
          borderRadius: 2,
          background: "transparent",
          position: "relative",
          height: "100%",
          width: "100%",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          p: 2,
        }}
      >
        <Alert severity="info">{t("publicShare.media.previewNotAvailableFormat")}</Alert>
      </Paper>
    </Box>
  );
};

export default PublicShareMediaViewer;
