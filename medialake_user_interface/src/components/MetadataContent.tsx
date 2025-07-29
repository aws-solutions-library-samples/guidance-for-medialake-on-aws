import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  useTheme,
  alpha,
} from "@mui/material";
import { formatCamelCase } from "../utils/stringUtils";
import { TruncatedTextWithTooltip } from "./common/TruncatedTextWithTooltip";

// Output filters for metadata categories
export const outputFilters = {
  "Image (IFD0)": ["ImageWidth", "ImageHeight", "Make", "Model", "Software"],
  EXIF: [
    "ExposureTime",
    "ShutterSpeedValue",
    "FNumber",
    "ApertureValue",
    "ISO",
    "LensModel",
  ],
  GPS: ["GPSLatitude", "GPSLongitude", "GPSAltitude"],
  "Thumbnail (IFD1)": ["ImageWidth", "ImageHeight", "ThumbnailLength"],
  IPTC: ["Headline", "Byline", "Credit", "Caption", "Source", "Country"],
  ICC: [
    "ProfileVersion",
    "ProfileClass",
    "ColorSpaceData",
    "ProfileConnectionSpace",
    "ProfileFileSignature",
    "DeviceManufacturer",
    "RenderingIntent",
    "ProfileCreator",
    "ProfileDescription",
  ],
  XMP: ["Creator", "Title", "Description", "Rights"],
  "JFIF (JPEG only)": [
    "JFIFVersion",
    "ResolutionUnit",
    "XResolution",
    "YResolution",
  ],
  "IHDR (PNG only)": [
    "Width",
    "Height",
    "BitDepth",
    "ColorType",
    "CompressionMethod",
    "FilterMethod",
    "InterlaceMethod",
  ],
  "Maker Note": [],
  "User Comment": [],
  Rights: ["UsageTerms", "CopyrightNotice", "WebStatement"],
  "IPTC Core": ["CreatorContactInfo", "Scene"],
  "IPTC Extension": ["PersonInImage", "LocationCreated"],
  Photoshop: ["Category", "SupplementalCategories", "AuthorsPosition"],
  PLUS: ["LicenseID", "ImageCreator", "CopyrightOwner"],
  "Dublin Core": ["Format", "Type", "Identifier"],
  "XMP Media Management": ["DerivedFrom", "DocumentID", "InstanceID"],
  Auxiliary: ["Lens", "SerialNumber"],
  "Camera Raw Settings": [
    "Version",
    "ProcessVersion",
    "WhiteBalance",
    "Temperature",
    "Tint",
  ],
  "EXIF Extended": ["Gamma", "CameraOwnerName", "BodySerialNumber"],
  "XMP Dynamic Media": [
    "AudioSampleRate",
    "AudioChannelType",
    "VideoFrameRate",
    "StartTimeScale",
    "Duration",
  ],
  Interoperability: ["InteroperabilityIndex", "InteroperabilityVersion"],
};

interface MetadataContentProps {
  data: any;
  depth?: number;
  showAll: boolean;
  category?: string;
  mediaType?: "image" | "audio" | "video";
}

const MetadataContent: React.FC<MetadataContentProps> = ({
  data,
  depth = 0,
  showAll,
  category,
  mediaType = "image",
}) => {
  const theme = useTheme();

  const sortEntries = (entries: [string, any][]): [string, any][] => {
    if (category && outputFilters[category]) {
      const preferredOrder = outputFilters[category];
      return [
        ...preferredOrder
          .map((key) => entries.find(([k]) => k === key))
          .filter(Boolean),
        ...entries.filter(([key]) => !preferredOrder.includes(key)),
      ];
    }
    return entries;
  };

  // Function to flatten nested objects like Tags/Encoder
  const flattenNestedMetadata = (entries: [string, any][]): [string, any][] => {
    const result: [string, any][] = [];

    entries.forEach(([key, value]) => {
      if (
        typeof value === "object" &&
        value !== null &&
        !Array.isArray(value) &&
        Object.keys(value).length > 0
      ) {
        // Mark this as a parent with _PARENT_ prefix (for internal use)
        result.push([`_PARENT_${key}`, ""]);

        // Then add the child properties with a visible indent prefix
        Object.entries(value).forEach(([subKey, subValue]) => {
          result.push([`      ↳ ${subKey}`, subValue]);
        });
      } else {
        result.push([key, value]);
      }
    });

    return result;
  };

  // Function to identify parent-child relationships in entries
  const isParentEntry = (key: string): boolean => {
    return key.startsWith("_PARENT_");
  };

  // Function to clean display keys (remove internal markings)
  const cleanDisplayKey = (key: string): string => {
    if (key.startsWith("_PARENT_")) {
      return key.substring(8); // Remove the _PARENT_ prefix
    }
    return key;
  };

  if (Array.isArray(data)) {
    const displayData = showAll ? data : data.slice(0, 5);
    return (
      <List dense disablePadding>
        {displayData.map((item, index) => (
          <ListItem key={index} sx={{ pl: depth * 2 }}>
            <MetadataContent
              data={item}
              depth={depth + 1}
              showAll={showAll}
              category={category}
              mediaType={mediaType}
            />
          </ListItem>
        ))}
      </List>
    );
  } else if (typeof data === "object" && data !== null) {
    let entries = Object.entries(data);
    // Filter out keys that contain "Metadata" to hide them from display
    entries = entries.filter(([key]) => !key.includes("Metadata"));
    const sortedEntries = sortEntries(entries);
    // Flatten nested metadata
    const flattenedEntries = flattenNestedMetadata(sortedEntries);
    const displayEntries = showAll
      ? flattenedEntries
      : flattenedEntries.slice(0, 5);

    // Create rows with simple key-value pairs (one per row)
    const rows: [string, any][] = displayEntries.map(([key, value]) => {
      if (isParentEntry(key)) {
        return [cleanDisplayKey(key), value];
      }
      return [key, value];
    });

    return (
      <Box
        sx={{
          width: "100%",
          mb: 2,
          backgroundColor: alpha(theme.palette.background.paper, 0.3),
          borderRadius: 1,
          p: 2,
        }}
      >
        {rows.map(([key, value], rowIndex) => (
          <Box
            key={rowIndex}
            sx={{
              display: "grid",
              gridTemplateColumns: "auto 1fr",
              gap: 3,
              py: 1,
              borderBottom:
                rowIndex < rows.length - 1
                  ? `1px solid ${alpha(theme.palette.divider, 0.1)}`
                  : "none",
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontWeight: "bold",
                color: key.trim().startsWith("↳")
                  ? theme.palette.primary.main
                  : theme.palette.text.secondary,
                textAlign: "left",
                minWidth: "max-content",
              }}
            >
              {formatCamelCase(key)}
            </Typography>
            <Box>
              {typeof value === "object" && value !== null ? (
                <MetadataContent
                  data={value}
                  depth={depth + 1}
                  showAll={showAll}
                  category={category}
                  mediaType={mediaType}
                />
              ) : (
                <Typography
                  variant="body2"
                  sx={{
                    wordBreak: "break-word",
                    whiteSpace: "normal",
                  }}
                >
                  {String(value)}
                </Typography>
              )}
            </Box>
          </Box>
        ))}
      </Box>
    );
  } else {
    return <Typography variant="body2">{String(data)}</Typography>;
  }
};

export default MetadataContent;
