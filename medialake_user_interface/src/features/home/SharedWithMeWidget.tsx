import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  Skeleton,
  Stack,
  Avatar,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Folder as FolderIcon,
  PersonOutline as PersonIcon,
  Visibility as ViewerIcon,
  Edit as EditorIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetCollectionsSharedWithMe, type Collection } from "@/api/hooks/useCollections";
import { formatDate } from "@/utils/dateFormat";

interface SharedWithMeWidgetProps {
  maxItems?: number;
}

export const SharedWithMeWidget: React.FC<SharedWithMeWidgetProps> = ({ maxItems = 4 }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const theme = useTheme();

  const { data: collectionsResponse, isLoading, error } = useGetCollectionsSharedWithMe();

  const collections = collectionsResponse?.data?.slice(0, maxItems) || [];

  const handleCollectionClick = (collection: Collection) => {
    navigate(`/collections/${collection.id}/view`);
  };

  const getRoleBadge = (role?: string) => {
    const normalizedRole = role?.toUpperCase() || "VIEWER";
    switch (normalizedRole) {
      case "EDITOR":
        return (
          <Chip
            icon={<EditorIcon sx={{ fontSize: 14 }} />}
            label={t("collections.roles.editor", "Editor")}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ height: 24, fontSize: "0.75rem" }}
          />
        );
      case "VIEWER":
      default:
        return (
          <Chip
            icon={<ViewerIcon sx={{ fontSize: 14 }} />}
            label={t("collections.roles.viewer", "Viewer")}
            size="small"
            variant="outlined"
            sx={{ height: 24, fontSize: "0.75rem" }}
          />
        );
    }
  };

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          {t("home.sharedWithMe", "Shared With Me")}
        </Typography>
        <Stack direction="row" spacing={2} sx={{ overflowX: "auto", pb: 1 }}>
          {[1, 2, 3, 4].map((i) => (
            <Skeleton
              key={i}
              variant="rectangular"
              width={240}
              height={140}
              sx={{ borderRadius: 2, flexShrink: 0 }}
            />
          ))}
        </Stack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          {t("home.sharedWithMe", "Shared With Me")}
        </Typography>
        <Typography color="error" variant="body2">
          {t("common.errors.loadFailed", "Failed to load data")}
        </Typography>
      </Box>
    );
  }

  if (collections.length === 0) {
    return (
      <Box>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          {t("home.sharedWithMe", "Shared With Me")}
        </Typography>
        <Box
          sx={{
            textAlign: "center",
            py: 4,
            px: 2,
            backgroundColor: alpha(theme.palette.primary.main, 0.04),
            borderRadius: 2,
            border: `1px dashed ${alpha(theme.palette.primary.main, 0.2)}`,
          }}
        >
          <FolderIcon sx={{ fontSize: 48, color: "text.secondary", mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {t("home.noSharedCollections", "No collections have been shared with you yet")}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {t("home.sharedWithMe", "Shared With Me")}
        </Typography>
        {collectionsResponse?.data && collectionsResponse.data.length > maxItems && (
          <Typography
            variant="body2"
            color="primary"
            sx={{ cursor: "pointer", "&:hover": { textDecoration: "underline" } }}
            onClick={() => navigate("/collections?filter=sharedWithMe")}
          >
            {t("common.viewAll", "View All")} ({collectionsResponse.data.length})
          </Typography>
        )}
      </Box>

      <Stack direction="row" spacing={2} sx={{ overflowX: "auto", pb: 1 }}>
        {collections.map((collection) => (
          <Card
            key={collection.id}
            sx={{
              minWidth: 240,
              maxWidth: 280,
              flexShrink: 0,
              transition: "transform 0.2s, box-shadow 0.2s",
              "&:hover": {
                transform: "translateY(-4px)",
                boxShadow: theme.shadows[4],
              },
            }}
          >
            <CardActionArea onClick={() => handleCollectionClick(collection)}>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5, mb: 1.5 }}>
                  <Avatar
                    sx={{
                      bgcolor: alpha(theme.palette.primary.main, 0.1),
                      color: "primary.main",
                      width: 40,
                      height: 40,
                    }}
                  >
                    <FolderIcon />
                  </Avatar>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="subtitle1"
                      sx={{
                        fontWeight: 600,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {collection.name}
                    </Typography>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mt: 0.5 }}>
                      <PersonIcon sx={{ fontSize: 14, color: "text.secondary" }} />
                      <Typography variant="caption" color="text.secondary">
                        {collection.ownerName || collection.ownerId}
                      </Typography>
                    </Box>
                  </Box>
                </Box>

                {collection.description && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      mb: 1.5,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                    }}
                  >
                    {collection.description}
                  </Typography>
                )}

                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mt: 1,
                  }}
                >
                  {getRoleBadge(collection.myRole)}
                  <Typography variant="caption" color="text.secondary">
                    {collection.sharedAt && formatDate(collection.sharedAt)}
                  </Typography>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
};

export default SharedWithMeWidget;
