import React from "react";
import {
  Box,
  Grid,
  Typography,
  CircularProgress,
  Button,
  useTheme,
  alpha,
} from "@mui/material";
import { formatFileSize } from "../../utils/imageUtils";
import { formatLocalDateTime } from "../../shared/utils/dateUtils";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import AssetCard from "./AssetCard";

export interface RelatedItem {
  id: string;
  title: string;
  type: string;
  thumbnail?: string;
  proxyUrl?: string;
  score: number;
  format: string;
  fileSize: number;
  createDate: string;
}

export interface RelatedItemsViewProps {
  items: RelatedItem[];
  isLoading: boolean;
  onLoadMore: () => void;
  hasMore: boolean;
  viewMode?: "grid" | "list";
  onItemClick?: (item: RelatedItem) => void;
}

export const RelatedItemsView: React.FC<RelatedItemsViewProps> = ({
  items,
  isLoading,
  onLoadMore,
  hasMore,
  viewMode = "grid",
  onItemClick,
}) => {
  const theme = useTheme();
  console.log("RelatedItemsView - Received items:", items);
  console.log("RelatedItemsView - isLoading:", isLoading);

  const defaultFields = [
    { id: "name", label: "Name", visible: true },
    { id: "type", label: "Type", visible: true },
    { id: "format", label: "Format", visible: true },
    { id: "size", label: "Size", visible: true },
    { id: "createdAt", label: "Created", visible: true },
  ];

  const renderField = (fieldId: string, item: RelatedItem) => {
    switch (fieldId) {
      case "name":
        return item.title;
      case "type":
        return item.type.toUpperCase();
      case "format":
        return item.format;
      case "size":
        return formatFileSize(item.fileSize);
      case "createdAt":
        return formatLocalDateTime(item.createDate);
      default:
        return "";
    }
  };

  if (isLoading && items.length === 0) {
    console.log("RelatedItemsView - Showing loading state");
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (items.length === 0) {
    console.log("RelatedItemsView - No items to display");
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography color="text.secondary">No related items found</Typography>
      </Box>
    );
  }

  console.log("RelatedItemsView - Rendering grid with items:", items);
  return (
    <Box
      sx={{
        p: 2,
        backgroundColor: alpha(theme.palette.background.paper, 0.5),
        borderRadius: 1,
      }}
    >
      <Grid container spacing={3}>
        {items.map((item) => (
          <Grid item xs={12} sm={6} md={4} key={item.id}>
            <AssetCard
              id={item.id}
              name={item.title}
              thumbnailUrl={item.thumbnail}
              proxyUrl={item.proxyUrl}
              assetType={item.type}
              fields={defaultFields}
              renderField={(fieldId) => renderField(fieldId, item)}
              onAssetClick={() => onItemClick?.(item)}
              onDeleteClick={() => {}} // Not needed for related items
              onDownloadClick={() => {}} // Not needed for related items
              cardSize="medium"
              aspectRatio="square"
              thumbnailScale="fill"
              showMetadata={true}
              isFavorite={false} // Default to false since we don't have favorite info here
              onFavoriteToggle={(e) =>
                console.log(
                  "Favorite toggle not implemented in RelatedItemsView",
                )
              }
            />
          </Grid>
        ))}
      </Grid>

      {hasMore && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 3 }}>
          <Button
            variant="outlined"
            onClick={onLoadMore}
            disabled={isLoading}
            startIcon={
              isLoading ? <CircularProgress size={20} /> : <ExpandMoreIcon />
            }
          >
            Load More
          </Button>
        </Box>
      )}
    </Box>
  );
};
