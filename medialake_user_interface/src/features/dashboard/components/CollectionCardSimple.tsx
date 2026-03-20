import React from "react";
import { Box, Card, CardContent, Typography, Chip, alpha, useTheme } from "@mui/material";
import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Public as PublicIcon,
  Lock as PrivateIcon,
  Work,
  Campaign,
  Assignment,
  Archive,
  PhotoLibrary as PhotoLibraryIcon,
  Label,
  Movie,
  Collections as CollectionsIcon,
  Dashboard,
  Storage,
  Inventory,
  Category,
  BookmarkBorder,
  LocalOffer,
} from "@mui/icons-material";
import type { SvgIconComponent } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { ALL_ICONS } from "@/components/collections/ThumbnailSelector";

// Map of icon names to Material-UI icon components
const ICON_MAP: Record<string, SvgIconComponent> = {
  Folder: FolderIcon,
  FolderOpen: FolderOpenIcon,
  Work: Work,
  Campaign: Campaign,
  Assignment: Assignment,
  Archive: Archive,
  PhotoLibrary: PhotoLibraryIcon,
  Label: Label,
  Movie: Movie,
  Collections: CollectionsIcon,
  Dashboard: Dashboard,
  Storage: Storage,
  Inventory: Inventory,
  Category: Category,
  BookmarkBorder: BookmarkBorder,
  LocalOffer: LocalOffer,
};

export interface CollectionCardSimpleProps {
  name: string;
  itemCount: number;
  childCollectionCount?: number;
  isPublic: boolean;
  iconName?: string;
  color?: string;
  thumbnailType?: string;
  thumbnailValue?: string;
  thumbnailUrl?: string;
  onClick: () => void;
}

export const CollectionCardSimple: React.FC<CollectionCardSimpleProps> = ({
  name,
  itemCount,
  childCollectionCount = 0,
  isPublic,
  iconName,
  color,
  thumbnailType,
  thumbnailValue,
  thumbnailUrl,
  onClick,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  // Resolve the thumbnail/icon to display
  const renderThumbnail = () => {
    // Priority 1: Icon thumbnail from ThumbnailSelector
    if (thumbnailType === "icon" && thumbnailValue) {
      const ThumbnailIcon = ALL_ICONS[thumbnailValue];
      if (ThumbnailIcon) {
        return (
          <ThumbnailIcon sx={{ fontSize: 48, color: alpha(theme.palette.primary.main, 0.18) }} />
        );
      }
    }

    // Priority 2: Uploaded/asset/frame thumbnail image
    if (thumbnailUrl && thumbnailType !== "icon") {
      return (
        <Box
          component="img"
          src={thumbnailUrl}
          alt={name}
          sx={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      );
    }

    // Priority 3: Collection type icon
    if (iconName && ICON_MAP[iconName]) {
      const IconComp = ICON_MAP[iconName];
      return (
        <IconComp
          sx={{
            fontSize: 48,
            color: color ? alpha(color, 0.3) : alpha(theme.palette.primary.main, 0.18),
          }}
        />
      );
    }

    // Fallback
    return <FolderIcon sx={{ fontSize: 48, color: alpha(theme.palette.primary.main, 0.18) }} />;
  };

  return (
    <Card
      onClick={onClick}
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        cursor: "pointer",
        borderRadius: 3,
        overflow: "hidden",
        border: "1px solid",
        borderColor: alpha(theme.palette.divider, 0.1),
        bgcolor: "background.paper",
        transition:
          "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
        "&:hover": {
          transform: "translateY(-4px)",
          boxShadow: `0 8px 32px ${alpha(theme.palette.common.black, 0.2)}`,
        },
      }}
    >
      {/* Thumbnail area */}
      <Box sx={{ p: 1, pb: 0 }}>
        <Box
          sx={{
            height: 120,
            borderRadius: 2.5,
            overflow: "hidden",
            bgcolor:
              thumbnailUrl && thumbnailType !== "icon"
                ? "transparent"
                : alpha(theme.palette.primary.main, 0.04),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {renderThumbnail()}
        </Box>
      </Box>

      {/* Info section */}
      <CardContent sx={{ px: 1.5, pt: 1, pb: 1, "&:last-child": { pb: 1 } }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
          <FolderIcon sx={{ fontSize: 16, color: alpha(theme.palette.primary.main, 0.5) }} />
          <Typography
            variant="subtitle2"
            component="h4"
            sx={{
              fontWeight: 600,
              fontSize: "0.82rem",
              lineHeight: 1.4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
          >
            {name}
          </Typography>
        </Box>

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.7rem" }}>
            {itemCount} asset{itemCount !== 1 ? "s" : ""}
            {childCollectionCount > 0 && ` · ${childCollectionCount} sub`}
          </Typography>
          <Chip
            label={isPublic ? t("common.public", "Public") : t("common.private", "Private")}
            size="small"
            icon={isPublic ? <PublicIcon /> : <PrivateIcon />}
            variant="outlined"
            sx={{
              height: 20,
              fontSize: "0.65rem",
              fontWeight: 500,
              color: isPublic ? "success.main" : "text.secondary",
              borderColor: isPublic
                ? alpha(theme.palette.success.main, 0.35)
                : alpha(theme.palette.text.secondary, 0.15),
              bgcolor: isPublic ? alpha(theme.palette.success.main, 0.06) : "transparent",
              "& .MuiChip-icon": {
                color: isPublic ? "success.main" : "text.secondary",
                fontSize: 12,
              },
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
};
