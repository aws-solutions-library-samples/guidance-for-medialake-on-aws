import React, { useState, useCallback, useMemo, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  CircularProgress,
  Breadcrumbs,
  Link,
  Paper,
  Divider,
  Button,
  TextField,
  IconButton,
  Menu,
  MenuItem,
  useTheme,
  alpha,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import { useS3Explorer } from "../../api/hooks/useS3Explorer";
import { formatFileSize } from "../../common/helpers/utils";
import { useQueryClient } from "@tanstack/react-query";
import { useErrorModal } from "../../hooks/useErrorModal";
import { QUERY_KEYS } from "../../api/queryKeys";
import { API_ENDPOINTS } from "../../api/endpoints";
import { apiClient } from "../../api/apiClient";
import { logger } from "../../common/helpers/logger";
import type {
  ApiResponse,
  S3ListObjectsResponse,
  S3Object,
} from "../../api/types/api.types";

interface S3ExplorerProps {
  connectorId: string;
}

export const S3Explorer: React.FC<S3ExplorerProps> = ({ connectorId }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [currentPath, setCurrentPath] = useState<string>("");
  const [continuationToken, setContinuationToken] = useState<string | null>(
    null,
  );
  const [nameFilter, setNameFilter] = useState<string>("");
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedObject, setSelectedObject] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const queryClient = useQueryClient();

  const breadcrumbPaths = useMemo(() => {
    const paths = currentPath.split("/").filter(Boolean);
    return ["", ...paths];
  }, [currentPath]);

  const { data, isLoading, error } = useS3Explorer({
    connectorId,
    prefix: currentPath,
    delimiter: "/",
    continuationToken,
  });

  const s3Data = data
    ? (data as ApiResponse<S3ListObjectsResponse>).data
    : undefined;

  useEffect(() => {
    const startTime = performance.now();
    return () => {
      logger.debug(
        `S3Explorer component mounted for ${performance.now() - startTime}ms`,
      );
    };
  }, []);

  useEffect(() => {
    if (data && isInitialLoad) {
      setIsInitialLoad(false);
    }
  }, [data, isInitialLoad]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString(undefined, {
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const handlePathClick = useCallback((path: string) => {
    setCurrentPath(path);
    setContinuationToken(null);
  }, []);

  const handleLoadMore = useCallback(() => {
    if (s3Data?.nextContinuationToken) {
      setContinuationToken(s3Data.nextContinuationToken);
    }
  }, [s3Data?.nextContinuationToken]);

  const handleMenuClick = (
    event: React.MouseEvent<HTMLElement>,
    objectKey: string,
  ) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setSelectedObject(objectKey);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedObject(null);
  };

  const handleFolderHover = useCallback(
    (prefix: string) => {
      queryClient.prefetchQuery({
        queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(connectorId, prefix, null),
        queryFn: async () => {
          const response = await apiClient.get(
            `${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`,
            { params: { prefix, delimiter: "/" } },
          );
          return response.data;
        },
      });
    },
    [connectorId, queryClient],
  );

  const filteredObjects = useMemo(() => {
    if (!s3Data?.objects) return [];
    return s3Data.objects.filter((obj) =>
      obj.Key.toLowerCase().includes(nameFilter.toLowerCase()),
    );
  }, [s3Data?.objects, nameFilter]);

  const filteredPrefixes = useMemo(() => {
    if (!s3Data?.commonPrefixes) return [];
    return s3Data.commonPrefixes.filter((prefix) =>
      prefix.toLowerCase().includes(nameFilter.toLowerCase()),
    );
  }, [s3Data?.commonPrefixes, nameFilter]);

  const renderFolders = () => {
    return filteredPrefixes.map((prefix) => (
      <ListItem
        key={prefix}
        onClick={() => handlePathClick(prefix)}
        onMouseEnter={() => handleFolderHover(prefix)}
        sx={{
          cursor: "pointer",
          borderRadius: "8px",
          my: 0.5,
          "&:hover": {
            backgroundColor: alpha(theme.palette.primary.main, 0.02),
          },
          transition: "background-color 0.2s ease",
        }}
      >
        <ListItemIcon>
          <FolderIcon sx={{ color: theme.palette.primary.main }} />
        </ListItemIcon>
        <ListItemText
          primary={
            <Typography
              variant="body2"
              sx={{ fontWeight: 500, color: theme.palette.primary.main }}
            >
              {prefix.split("/").slice(-2)[0]}
            </Typography>
          }
          secondary={
            <Typography
              variant="caption"
              sx={{ color: theme.palette.text.secondary }}
            >
              {t("common.folder")}
            </Typography>
          }
        />
      </ListItem>
    ));
  };

  const renderFiles = () => {
    return filteredObjects.map((object) => (
      <ListItem
        key={object.Key}
        sx={{
          borderRadius: "8px",
          my: 0.5,
          "&:hover": {
            backgroundColor: alpha(theme.palette.primary.main, 0.02),
          },
          transition: "background-color 0.2s ease",
        }}
      >
        <ListItemIcon>
          <InsertDriveFileIcon sx={{ color: theme.palette.text.secondary }} />
        </ListItemIcon>
        <ListItemText
          primary={
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {object.Key.split("/").pop()}
            </Typography>
          }
          secondary={
            <Typography
              variant="caption"
              sx={{ color: theme.palette.text.secondary }}
            >
              {t("s3Explorer.file.info", {
                size: formatFileSize(object.Size),
                storageClass: object.StorageClass,
                modified: formatDate(object.LastModified),
              })}
            </Typography>
          }
        />
      </ListItem>
    ));
  };

  if (isLoading) {
    return (
      <Box
        display="flex"
        flexDirection="column"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <CircularProgress />
        <Typography variant="body2" sx={{ mt: 2 }}>
          {isInitialLoad
            ? t("s3Explorer.loading.initializing", "Loading...")
            : t("s3Explorer.loading.fetchingContents", "Fetching contents...")}
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={3}>
        <Typography color="error">
          {t("s3Explorer.error.loading", { message: (error as Error).message })}
        </Typography>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Box mb={2}>
        <TextField
          label={t("s3Explorer.filter.label")}
          variant="outlined"
          size="small"
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          fullWidth
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: "8px",
              backgroundColor: theme.palette.background.paper,
            },
          }}
        />
      </Box>

      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 2,
          borderRadius: "12px",
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        }}
      >
        <Breadcrumbs>
          {breadcrumbPaths.map((path, index) => {
            const fullPath =
              breadcrumbPaths.slice(1, index + 1).join("/") +
              (index > 0 ? "/" : "");
            return (
              <Link
                key={path || "root"}
                component="button"
                onClick={() => handlePathClick(fullPath)}
                sx={{
                  textDecoration: "none",
                  color: theme.palette.primary.main,
                  "&:hover": {
                    textDecoration: "underline",
                  },
                }}
              >
                {path || t("common.root")}
              </Link>
            );
          })}
        </Breadcrumbs>
      </Paper>

      <Paper
        elevation={0}
        sx={{
          borderRadius: "12px",
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          backgroundColor: theme.palette.background.paper,
        }}
      >
        <List sx={{ p: 1 }}>
          {renderFolders()}
          {filteredPrefixes.length && filteredObjects.length ? (
            <Divider sx={{ my: 1 }} />
          ) : null}
          {renderFiles()}
        </List>
      </Paper>

      {s3Data?.isTruncated && (
        <Box mt={2} display="flex" justifyContent="center">
          <Button
            variant="contained"
            onClick={handleLoadMore}
            sx={{
              borderRadius: "8px",
              textTransform: "none",
              px: 3,
              backgroundColor: theme.palette.primary.main,
              "&:hover": {
                backgroundColor: theme.palette.primary.dark,
              },
            }}
          >
            {t("common.loadMore")}
          </Button>
        </Box>
      )}
    </Box>
  );
};
