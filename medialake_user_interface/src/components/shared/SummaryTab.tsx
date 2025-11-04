import React from "react";
import { Box, Typography } from "@mui/material";
import { formatFileSize } from "../../utils/imageUtils";
import TabContentContainer from "../common/TabContentContainer";

const FILE_INFO_COLOR = "#4299E1";
const TECH_DETAILS_COLOR = "#68D391";

interface MetadataFieldProps {
  label: string;
  value: string | number;
}

const MetadataField: React.FC<MetadataFieldProps> = ({ label, value }) => (
  <Box sx={{ display: "flex", mb: 1 }}>
    <Typography
      sx={{
        width: "120px",
        color: "text.secondary",
        fontSize: "0.875rem",
      }}
    >
      {label}:
    </Typography>
    <Typography sx={{ flex: 1, fontSize: "0.875rem", wordBreak: "break-all" }}>
      {value}
    </Typography>
  </Box>
);

interface SectionHeaderProps {
  title: string;
  color: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ title, color }) => (
  <>
    <Typography
      sx={{
        color: color,
        fontSize: "0.875rem",
        fontWeight: 600,
        mb: 0.5,
      }}
    >
      {title}
    </Typography>
    <Box
      sx={{
        width: "100%",
        height: "1px",
        bgcolor: color,
        mb: 2,
      }}
    />
  </>
);

interface FileInfoSectionProps {
  assetData: any;
}

export const FileInfoSection: React.FC<FileInfoSectionProps> = ({
  assetData,
}) => {
  const s3Bucket =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.Bucket;
  const objectName =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.ObjectKey?.Name;
  const fullPath =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.ObjectKey?.FullPath;
  const s3Uri =
    s3Bucket && fullPath ? `s3://${s3Bucket}/${fullPath}` : "Unknown";

  const fileSize =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo
      ?.PrimaryLocation?.FileInfo?.Size || 0;
  const format =
    assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format ||
    "Unknown";
  const assetType =
    assetData?.data?.asset?.DigitalSourceAsset?.Type || "Unknown";

  return (
    <Box sx={{ mb: 3 }}>
      <SectionHeader title="File Information" color={FILE_INFO_COLOR} />
      <MetadataField label="Type" value={assetType} />
      <MetadataField label="Size" value={formatFileSize(fileSize)} />
      <MetadataField label="Format" value={format} />
      <MetadataField label="S3 Bucket" value={s3Bucket || "Unknown"} />
      <MetadataField label="Object Name" value={objectName || "Unknown"} />
      <MetadataField label="S3 URI" value={s3Uri} />
    </Box>
  );
};

interface AudioSummaryTabProps {
  assetData: any;
}

export const AudioSummaryTab: React.FC<AudioSummaryTabProps> = ({
  assetData,
}) => {
  const metadata = assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {};
  const general = metadata.general || {};
  const audio = Array.isArray(metadata.audio) ? metadata.audio[0] : {};

  const duration =
    audio.duration != null
      ? audio.duration.toFixed(2)
      : general.Duration
        ? parseFloat(general.Duration).toFixed(2)
        : "Unknown";
  const sampleRate = audio.sample_rate
    ? (parseInt(audio.sample_rate, 10) / 1000).toFixed(1)
    : "Unknown";
  const bitDepth = audio.BitsPerSample || audio.bit_depth || "Unknown";
  const channels = audio.channels || audio.Channels || "Unknown";
  const bitRate = audio.bit_rate
    ? `${Math.round(audio.bit_rate / 1000)} kbps`
    : "Unknown";
  const codec = audio.codec_name || general.Format || "Unknown";
  const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
    ? new Date(
        assetData.data.asset.DigitalSourceAsset.CreateDate,
      ).toLocaleDateString()
    : "Unknown";

  return (
    <TabContentContainer>
      <FileInfoSection assetData={assetData} />
      <Box sx={{ mb: 3 }}>
        <SectionHeader title="Technical Details" color={TECH_DETAILS_COLOR} />
        <MetadataField label="Duration" value={`${duration} seconds`} />
        <MetadataField label="Sample Rate" value={`${sampleRate} kHz`} />
        <MetadataField label="Bit Depth" value={`${bitDepth} bit`} />
        <MetadataField label="Channels" value={channels} />
        <MetadataField label="Bit Rate" value={bitRate} />
        <MetadataField label="Codec" value={codec} />
        <MetadataField label="Created Date" value={createdDate} />
      </Box>
    </TabContentContainer>
  );
};

interface VideoSummaryTabProps {
  assetData: any;
}

export const VideoSummaryTab: React.FC<VideoSummaryTabProps> = ({
  assetData,
}) => {
  const metadata = assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {};
  const generalMetadata = metadata.general || {};
  const videoMetadata = Array.isArray(metadata.video) ? metadata.video[0] : {};

  const duration = generalMetadata.Duration
    ? `${parseFloat(generalMetadata.Duration).toFixed(2)} s`
    : "Unknown";
  const width = videoMetadata.Width ?? "Unknown";
  const height = videoMetadata.Height ?? "Unknown";
  const frameRate = videoMetadata.FrameRate
    ? `${videoMetadata.FrameRate} FPS`
    : "Unknown";
  const bitRate =
    videoMetadata.OverallBitRate || videoMetadata.BitRate
      ? `${Math.round((videoMetadata.OverallBitRate || videoMetadata.BitRate) / 1000)} kbps`
      : "Unknown";
  const codec =
    videoMetadata.codec_name || metadata.general.Format || "Unknown";
  const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
    ? new Date(
        assetData.data.asset.DigitalSourceAsset.CreateDate,
      ).toLocaleDateString()
    : "Unknown";

  return (
    <TabContentContainer>
      <FileInfoSection assetData={assetData} />
      <Box sx={{ mb: 3 }}>
        <SectionHeader title="Technical Details" color={TECH_DETAILS_COLOR} />
        <MetadataField label="Duration" value={`${duration} seconds`} />
        <MetadataField label="Resolution" value={`${width}x${height}`} />
        <MetadataField label="Frame Rate" value={`${frameRate} FPS`} />
        <MetadataField label="Bit Rate" value={bitRate} />
        <MetadataField label="Codec" value={codec} />
        <MetadataField label="Created Date" value={createdDate} />
      </Box>
    </TabContentContainer>
  );
};

interface ImageSummaryTabProps {
  assetData: any;
}

export const ImageSummaryTab: React.FC<ImageSummaryTabProps> = ({
  assetData,
}) => {
  const asset = assetData?.data?.asset;
  const metadata = asset?.Metadata?.EmbeddedMetadata || {};
  const generalMetadata = metadata?.General || {};
  const imageMetadata = metadata?.Image?.[0] || {};

  const width = imageMetadata?.Width || generalMetadata?.ImageWidth;
  const height = imageMetadata?.Height || generalMetadata?.ImageHeight;
  const dimensions = width && height ? `${width}x${height}` : "Unknown";
  const colorDepth =
    imageMetadata?.BitDepth || imageMetadata?.Bitdepth || "Unknown";
  const colorSpace =
    imageMetadata?.ColorSpace || imageMetadata?.Colorspace || "Unknown";
  const compression =
    imageMetadata?.Compression ||
    imageMetadata?.CompressionAlgorithm ||
    "Unknown";
  const createdDate = asset?.DigitalSourceAsset?.CreateDate
    ? new Date(asset.DigitalSourceAsset.CreateDate).toLocaleDateString()
    : "Unknown";

  return (
    <TabContentContainer>
      <FileInfoSection assetData={assetData} />
      <Box sx={{ mb: 3 }}>
        <SectionHeader title="Technical Details" color={TECH_DETAILS_COLOR} />
        <MetadataField label="Dimensions" value={dimensions} />
        <MetadataField label="Color Depth" value={`${colorDepth} bit`} />
        <MetadataField label="Color Space" value={colorSpace} />
        <MetadataField label="Compression" value={compression} />
        <MetadataField label="Created Date" value={createdDate} />
      </Box>
    </TabContentContainer>
  );
};
