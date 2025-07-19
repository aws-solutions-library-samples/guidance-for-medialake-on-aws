import React from "react";
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  CircularProgress,
  Button,
  useTheme,
  alpha,
} from "@mui/material";
import { formatFileSize } from "../../utils/imageUtils";
import { formatLocalDateTime } from "../../shared/utils/dateUtils";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import LinkOutlinedIcon from "@mui/icons-material/LinkOutlined";
import { RelatedItem } from "../../api/types/asset.types";

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

  const getItemIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "image":
        return (
          <DescriptionOutlinedIcon
            fontSize="small"
            sx={{ color: theme.palette.primary.main }}
          />
        );
      case "video":
        return (
          <CodeOutlinedIcon
            fontSize="small"
            sx={{ color: theme.palette.primary.main }}
          />
        );
      case "audio":
        return (
          <InfoOutlinedIcon
            fontSize="small"
            sx={{ color: theme.palette.primary.main }}
          />
        );
      default:
        return (
          <LinkOutlinedIcon
            fontSize="small"
            sx={{ color: theme.palette.primary.main }}
          />
        );
    }
  };

  if (isLoading && items.length === 0) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (items.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography color="text.secondary">No related items found</Typography>
      </Box>
    );
  }

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
            <Card
              variant="outlined"
              onClick={() => onItemClick?.(item)}
              sx={{
                height: "100%",
                transition: "all 0.2s ease-in-out",
                cursor: "pointer",
                "&:hover": {
                  boxShadow: `0 4px 8px ${alpha(theme.palette.common.black, 0.1)}`,
                  transform: "translateY(-2px)",
                },
              }}
            >
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                  {getItemIcon(item.type)}
                  <Typography
                    variant="subtitle1"
                    sx={{
                      ml: 1,
                      fontWeight: 600,
                      color: theme.palette.text.primary,
                    }}
                  >
                    {item.title}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1, mb: 1 }}>
                  <Chip
                    size="small"
                    label={item.type.toUpperCase()}
                    sx={{
                      backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      color: theme.palette.primary.main,
                      fontWeight: 500,
                      fontSize: "0.75rem",
                    }}
                  />
                  <Chip
                    size="small"
                    label={`Similarity: ${(item.score * 100).toFixed(1)}%`}
                    sx={{
                      backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                      color: theme.palette.secondary.main,
                      fontWeight: 500,
                      fontSize: "0.75rem",
                    }}
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {formatFileSize(item.fileSize)} • {item.format}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Created: {formatLocalDateTime(item.createDate)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {hasMore && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 3 }}>
          <Button
            variant="outlined"
            onClick={onLoadMore}
            startIcon={<ExpandMoreIcon />}
            disabled={isLoading}
          >
            {isLoading ? "Loading..." : "Load More"}
          </Button>
        </Box>
      )}
    </Box>
  );
};
