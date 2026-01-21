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
  AvatarGroup,
  Tooltip,
  alpha,
  useTheme,
  IconButton,
} from "@mui/material";
import {
  Folder as FolderIcon,
  People as PeopleIcon,
  Share as ShareIcon,
  Settings as ManageIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useGetCollectionsSharedByMe, type Collection } from "@/api/hooks/useCollections";
import { formatDate } from "@/utils/dateFormat";

interface SharedByMeWidgetProps {
  maxItems?: number;
  onManageSharing?: (collection: Collection) => void;
}

export const SharedByMeWidget: React.FC<SharedByMeWidgetProps> = ({
  maxItems = 4,
  onManageSharing,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const theme = useTheme();

  const { data: collectionsResponse, isLoading, error } = useGetCollectionsSharedByMe();

  const collections = collectionsResponse?.data?.slice(0, maxItems) || [];

  const handleCollectionClick = (collection: Collection) => {
    navigate(`/collections/${collection.id}/view`);
  };

  const handleManageClick = (e: React.MouseEvent<HTMLButtonElement>, collection: Collection) => {
    e.stopPropagation();
    onManageSharing?.(collection);
  };

  if (isLoading) {
    return (
      <Box>
        <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
          {t("home.sharedByMe", "Shared By Me")}
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
          {t("home.sharedByMe", "Shared By Me")}
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
          {t("home.sharedByMe", "Shared By Me")}
        </Typography>
        <Box
          sx={{
            textAlign: "center",
            py: 4,
            px: 2,
            backgroundColor: alpha(theme.palette.secondary.main, 0.04),
            borderRadius: 2,
            border: `1px dashed ${alpha(theme.palette.secondary.main, 0.2)}`,
          }}
        >
          <ShareIcon sx={{ fontSize: 48, color: "text.secondary", mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {t("home.noSharedByMe", "You haven't shared any collections yet")}
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {t("home.sharedByMe", "Shared By Me")}
        </Typography>
        {collectionsResponse?.data && collectionsResponse.data.length > maxItems && (
          <Typography
            variant="body2"
            color="primary"
            sx={{ cursor: "pointer", "&:hover": { textDecoration: "underline" } }}
            onClick={() => navigate("/collections?filter=sharedByMe")}
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
                      bgcolor: alpha(theme.palette.secondary.main, 0.1),
                      color: "secondary.main",
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
                    <Chip
                      icon={<PeopleIcon sx={{ fontSize: 14 }} />}
                      label={t("collections.sharedWithCount", "{{count}} recipients", {
                        count: collection.shareCount || 0,
                      })}
                      size="small"
                      variant="outlined"
                      color="secondary"
                      sx={{ height: 22, fontSize: "0.7rem", mt: 0.5 }}
                    />
                  </Box>
                </Box>

                {collection.sharedWith && collection.sharedWith.length > 0 && (
                  <Box sx={{ mb: 1.5 }}>
                    <AvatarGroup max={4} sx={{ justifyContent: "flex-start" }}>
                      {collection.sharedWith.map((share, index) => (
                        <Tooltip key={index} title={share.targetId}>
                          <Avatar
                            sx={{
                              width: 28,
                              height: 28,
                              fontSize: "0.75rem",
                              bgcolor: alpha(theme.palette.primary.main, 0.2),
                              color: "primary.main",
                            }}
                          >
                            {share.targetId.charAt(0).toUpperCase()}
                          </Avatar>
                        </Tooltip>
                      ))}
                    </AvatarGroup>
                  </Box>
                )}

                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mt: 1,
                  }}
                >
                  <Typography variant="caption" color="text.secondary">
                    {collection.itemCount || 0} {t("common.items", "items")}
                  </Typography>
                  {onManageSharing && (
                    <Tooltip title={t("collections.manageSharing", "Manage Sharing")}>
                      <IconButton
                        size="small"
                        onClick={(e) => handleManageClick(e, collection)}
                        sx={{
                          "&:hover": {
                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                          },
                        }}
                      >
                        <ManageIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
};

export default SharedByMeWidget;
