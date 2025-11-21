import React, {
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";
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
  Button,
  TextField,
  IconButton,
  useTheme,
  alpha,
  useMediaQuery,
  Skeleton,
  InputAdornment,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import HomeIcon from "@mui/icons-material/Home";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useS3Explorer } from "../../api/hooks/useS3Explorer";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "../../api/queryKeys";
import { API_ENDPOINTS } from "../../api/endpoints";
import { apiClient } from "../../api/apiClient";
import { logger } from "../../common/helpers/logger";
import type {
  ApiResponse,
  S3ListObjectsResponse,
} from "../../api/types/api.types";

interface S3ExplorerProps {
  connectorId: string;
  initialPath?: string;
  onPathChange?: (path: string) => void;
  restrictedBasePath?: string;
}

type VirtualizedItem = {
  type: "folder";
  data: string;
  key: string;
};

// Helper function to highlight matching text
const highlightMatch = (text: string, searchTerm: string) => {
  if (!searchTerm) return text;

  const lowerText = text.toLowerCase();
  const lowerSearch = searchTerm.toLowerCase();
  const startIndex = lowerText.indexOf(lowerSearch);

  if (startIndex === -1) return text;

  const beforeMatch = text.substring(0, startIndex);
  const match = text.substring(startIndex, startIndex + searchTerm.length);
  const afterMatch = text.substring(startIndex + searchTerm.length);

  return (
    <>
      {beforeMatch}
      <Box
        component="mark"
        sx={{
          backgroundColor: "warning.light",
          color: "warning.contrastText",
          fontWeight: 600,
          padding: "0 2px",
          borderRadius: "2px",
        }}
      >
        {match}
      </Box>
      {afterMatch}
    </>
  );
};

export const S3Explorer: React.FC<S3ExplorerProps> = ({
  connectorId,
  initialPath,
  onPathChange,
  restrictedBasePath,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [currentPath, setCurrentPath] = useState<string>(initialPath || "");
  const [continuationToken, setContinuationToken] = useState<string | null>(
    null,
  );
  const [nameFilter, setNameFilter] = useState<string>("");
  const [debouncedFilter, setDebouncedFilter] = useState<string>("");
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [hoverTimeout, setHoverTimeout] = useState<NodeJS.Timeout | null>(null);
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);
  const listContainerRef = useRef<HTMLDivElement>(null);
  const typeAheadBuffer = useRef<string>("");
  const typeAheadTimeout = useRef<NodeJS.Timeout | null>(null);
  const lastHoverPrefetchTime = useRef<number>(0);
  const prefetchedPrefixes = useRef<Set<string>>(new Set());

  // Helper function to normalize paths with trailing slash
  const normalizePath = useCallback((path: string): string => {
    if (!path) return "";
    return path.endsWith("/") ? path : `${path}/`;
  }, []);

  // Helper function to compute parent prefix from a given path
  const getParentPrefix = useCallback((path: string): string => {
    if (!path) return "";
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 0) return "";
    return segments.slice(0, -1).join("/") + (segments.length > 1 ? "/" : "");
  }, []);

  // Notify parent when path changes (ensure normalized with trailing slash for folders)
  useEffect(() => {
    if (onPathChange) {
      const normalizedPath = currentPath ? normalizePath(currentPath) : "";
      onPathChange(normalizedPath);
    }
  }, [currentPath, onPathChange, normalizePath]);

  // Debounce filter input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedFilter(nameFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [nameFilter]);

  // Build breadcrumb items with both label and fullPath
  const breadcrumbItems = useMemo(() => {
    if (restrictedBasePath) {
      // Restricted mode: show only segments within the prefix
      const normalizedBase = normalizePath(restrictedBasePath);
      const normalizedCurrent = normalizePath(currentPath);

      // Safety check: if current path doesn't start with base, fallback to base
      const pathToUse = normalizedCurrent.startsWith(normalizedBase)
        ? normalizedCurrent
        : normalizedBase;

      // Compute relative path from base
      const relativePath = pathToUse.slice(normalizedBase.length);
      const relativeSegments = relativePath.split("/").filter(Boolean);

      // Extract prefix root label (last segment of base or localized "Root")
      const baseSegments = normalizedBase.split("/").filter(Boolean);
      const prefixRootLabel =
        baseSegments[baseSegments.length - 1] || t("common.root");

      // Build items starting with prefix root
      const items = [
        {
          label: prefixRootLabel,
          fullPath: normalizedBase,
          isRoot: true,
          ariaLabel: t("s3Explorer.breadcrumbs.prefixRoot"),
        },
        ...relativeSegments.map((segment, index) => {
          const relativeFullPath =
            relativeSegments.slice(0, index + 1).join("/") + "/";
          return {
            label: segment,
            fullPath: normalizedBase + relativeFullPath,
            isRoot: false,
            ariaLabel: `${t("s3Explorer.breadcrumbs.navigateTo")} ${segment}`,
          };
        }),
      ];

      // Apply ellipsis if more than 4 items (prefix root + 3+ segments)
      if (items.length > 4) {
        return [
          items[0], // Prefix root
          { label: "...", fullPath: null, isRoot: false, ariaLabel: "..." }, // Ellipsis
          ...items.slice(-2), // Last two segments
        ];
      }

      return items;
    } else {
      // Unrestricted mode: original logic
      const paths = currentPath.split("/").filter(Boolean);
      const allItems = paths.map((segment, index) => {
        const fullPath = paths.slice(0, index + 1).join("/") + "/";
        return { label: segment, fullPath, isRoot: false };
      });

      // Add root item at the beginning
      const itemsWithRoot = [
        {
          label: "",
          fullPath: "",
          isRoot: true,
          ariaLabel: t("common.root"),
        },
        ...allItems.map((item) => ({
          ...item,
          ariaLabel: `${t("s3Explorer.breadcrumbs.navigateTo")} ${item.label}`,
        })),
      ];

      // If path is too deep (>4 levels), show Root > ... > Parent > Current
      if (itemsWithRoot.length > 4) {
        return [
          itemsWithRoot[0], // Root
          { label: "...", fullPath: null, isRoot: false, ariaLabel: "..." }, // Ellipsis (not clickable)
          ...itemsWithRoot.slice(-2), // Last two segments
        ];
      }
      return itemsWithRoot;
    }
  }, [currentPath, restrictedBasePath, normalizePath, t]);

  const { data, isLoading, error, refetch } = useS3Explorer({
    connectorId,
    prefix: currentPath,
    delimiter: "/",
    continuationToken,
    showInlineError: true, // Suppress global error modal since we handle errors inline
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

  const handlePathClick = useCallback(
    (path: string) => {
      // If restrictedBasePath is set, prevent navigation above it
      if (restrictedBasePath) {
        const normalizedPath = normalizePath(path);
        const normalizedBase = normalizePath(restrictedBasePath);

        // Allow empty path only if restrictedBasePath is also empty
        if (path === "" && restrictedBasePath !== "") {
          logger.debug(
            `Navigation blocked: attempted to navigate to root with restricted base "${restrictedBasePath}"`,
          );
          return; // Prevent navigation to root if we have a restricted base
        }

        // Prevent navigation above the restricted base path
        if (path !== "" && !normalizedPath.startsWith(normalizedBase)) {
          logger.debug(
            `Navigation blocked: path "${normalizedPath}" does not start with base "${normalizedBase}"`,
          );
          return; // Silently ignore attempts to navigate outside the restricted base
        }
      }

      setCurrentPath(path);
      setContinuationToken(null);
      setSelectedIndex(-1);
    },
    [restrictedBasePath, normalizePath],
  );

  const handleLoadMore = useCallback(() => {
    if (s3Data?.nextContinuationToken) {
      setContinuationToken(s3Data.nextContinuationToken);
    }
  }, [s3Data?.nextContinuationToken]);

  const handleFolderHover = useCallback(
    (prefix: string) => {
      // Throttle: only prefetch if enough time has passed since last prefetch
      const now = Date.now();
      const throttleMs = 500; // Throttle to max one prefetch per 500ms

      if (now - lastHoverPrefetchTime.current < throttleMs) {
        return;
      }

      // Clear existing timeout
      if (hoverTimeout) {
        clearTimeout(hoverTimeout);
      }

      // Set new timeout for prefetch (200ms delay)
      const timeout = setTimeout(() => {
        // Skip if already prefetched
        if (prefetchedPrefixes.current.has(prefix)) {
          return;
        }

        lastHoverPrefetchTime.current = Date.now();
        prefetchedPrefixes.current.add(prefix);

        queryClient.prefetchQuery({
          queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(
            connectorId,
            prefix,
            null,
          ),
          queryFn: async () => {
            const response = await apiClient.get(
              `${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`,
              { params: { prefix, delimiter: "/" } },
            );
            return response.data;
          },
        });
      }, 200);

      setHoverTimeout(timeout);
    },
    [connectorId, queryClient, hoverTimeout],
  );

  const handleFolderLeave = useCallback(() => {
    if (hoverTimeout) {
      clearTimeout(hoverTimeout);
      setHoverTimeout(null);
    }
  }, [hoverTimeout]);

  const filteredPrefixes = useMemo(() => {
    if (!s3Data?.commonPrefixes) return [];
    return s3Data.commonPrefixes.filter((prefix) =>
      prefix.toLowerCase().includes(debouncedFilter.toLowerCase()),
    );
  }, [s3Data?.commonPrefixes, debouncedFilter]);

  // Virtualized items contain only folders
  const virtualizedItems = useMemo<VirtualizedItem[]>(() => {
    return filteredPrefixes.map((prefix) => ({
      type: "folder",
      data: prefix,
      key: `folder-${prefix}`,
    }));
  }, [filteredPrefixes]);

  // Initialize virtualizer
  const virtualizer = useVirtualizer({
    count: virtualizedItems.length,
    getScrollElement: () => listContainerRef.current,
    estimateSize: () => 56,
    overscan: 10,
  });

  // Adjacent prefetch: prefetch next few visible folder items on scroll
  useEffect(() => {
    const virtualItems = virtualizer.getVirtualItems();
    if (virtualItems.length === 0) return;

    // Get the next 5 upcoming folder items from the visible range
    const lastVisibleIndex = virtualItems[virtualItems.length - 1]?.index ?? -1;
    const prefetchCount = 5;

    for (
      let i = lastVisibleIndex + 1;
      i <
      Math.min(lastVisibleIndex + prefetchCount + 1, virtualizedItems.length);
      i++
    ) {
      const item = virtualizedItems[i];
      if (item?.type === "folder") {
        const prefix = item.data as string;

        // Skip if already prefetched
        if (!prefetchedPrefixes.current.has(prefix)) {
          prefetchedPrefixes.current.add(prefix);

          // Prefetch in the background
          queryClient
            .prefetchQuery({
              queryKey: QUERY_KEYS.CONNECTORS.s3.explorer(
                connectorId,
                prefix,
                null,
              ),
              queryFn: async () => {
                const response = await apiClient.get(
                  `${API_ENDPOINTS.CONNECTORS}/s3/explorer/${connectorId}`,
                  { params: { prefix, delimiter: "/" } },
                );
                return response.data;
              },
            })
            .catch(() => {
              // Silently fail prefetch
              logger.debug(`Adjacent prefetch failed for ${prefix}`);
            });
        }
      }
    }
  }, [
    virtualizer.getVirtualItems(),
    connectorId,
    queryClient,
    virtualizedItems,
  ]);

  // Clamp selectedIndex when virtualizedItems change
  useEffect(() => {
    if (virtualizedItems.length === 0) {
      setSelectedIndex(-1);
    } else if (selectedIndex >= virtualizedItems.length) {
      setSelectedIndex(Math.min(selectedIndex, virtualizedItems.length - 1));
    }
  }, [virtualizedItems.length, selectedIndex]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!listContainerRef.current?.contains(document.activeElement)) {
        return;
      }

      // Type-ahead search: accumulate letters and find matching items
      if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();

        // Clear previous timeout
        if (typeAheadTimeout.current) {
          clearTimeout(typeAheadTimeout.current);
        }

        // Add character to buffer
        typeAheadBuffer.current += e.key.toLowerCase();

        // Find first matching item
        const matchIndex = virtualizedItems.findIndex((item) => {
          const name = (item.data as string).split("/").slice(-2)[0];
          return name.toLowerCase().startsWith(typeAheadBuffer.current);
        });

        if (matchIndex !== -1) {
          setSelectedIndex(matchIndex);
        }

        // Reset buffer after 500ms
        typeAheadTimeout.current = setTimeout(() => {
          typeAheadBuffer.current = "";
        }, 500);

        return;
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((prev) =>
            prev < virtualizedItems.length - 1 ? prev + 1 : prev,
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
          break;
        case "Enter":
          e.preventDefault();
          if (selectedIndex >= 0 && selectedIndex < virtualizedItems.length) {
            const item = virtualizedItems[selectedIndex];
            handlePathClick(item.data as string);
          }
          break;
        case "Backspace":
          e.preventDefault();
          if (currentPath) {
            const parentPath = getParentPrefix(currentPath);

            // In restricted mode, prevent going above the base
            if (restrictedBasePath) {
              const normalizedParent = normalizePath(parentPath);
              const normalizedBase = normalizePath(restrictedBasePath);
              if (normalizedParent.startsWith(normalizedBase)) {
                handlePathClick(parentPath);
              }
            } else {
              handlePathClick(parentPath);
            }
          }
          break;
        case "Home":
          e.preventDefault();
          setSelectedIndex(0);
          break;
        case "End":
          e.preventDefault();
          setSelectedIndex(virtualizedItems.length - 1);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (typeAheadTimeout.current) {
        clearTimeout(typeAheadTimeout.current);
      }
    };
  }, [
    selectedIndex,
    virtualizedItems,
    currentPath,
    handlePathClick,
    restrictedBasePath,
    normalizePath,
    getParentPrefix,
  ]);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex >= 0) {
      virtualizer.scrollToIndex(selectedIndex, { align: "center" });
    }
  }, [selectedIndex, virtualizer]);

  const renderErrorState = (error: any) => {
    const errorStatus = (error as any)?.status;
    // Read allowedPrefixes from error object first, fallback to s3Data for backward compatibility
    const allowedPrefixes =
      (error as any)?.allowedPrefixes || s3Data?.allowedPrefixes;

    let errorMessage = t("s3Explorer.error.loading", {
      message: error.message,
    });
    let showAllowedPrefixes = false;

    if (errorStatus === 403) {
      if (allowedPrefixes && allowedPrefixes.length > 0) {
        errorMessage = t("s3Explorer.error.permissionWithPrefixes", {
          prefixes: allowedPrefixes.join(", "),
        });
        showAllowedPrefixes = true;
      } else {
        errorMessage = t("s3Explorer.error.permission");
      }
    } else if (errorStatus === 404) {
      errorMessage = t("s3Explorer.error.notFound");
    } else if (errorStatus === 408 || errorStatus === 504) {
      errorMessage = t("s3Explorer.error.timeout");
    } else if (error.message?.includes("Network")) {
      errorMessage = t("s3Explorer.error.network");
    }

    return (
      <Box
        p={3}
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        minHeight="200px"
      >
        <Typography color="error" variant="body1" gutterBottom>
          {errorMessage}
        </Typography>
        {showAllowedPrefixes && allowedPrefixes && (
          <Box mt={2}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {t("s3Explorer.error.permissionWithPrefixes", { prefixes: "" })}
            </Typography>
            <Box component="ul" sx={{ mt: 1, pl: 2 }}>
              {allowedPrefixes.map((prefix: string) => (
                <Typography key={prefix} component="li" variant="body2">
                  {prefix}
                </Typography>
              ))}
            </Box>
          </Box>
        )}
        <Button variant="contained" onClick={() => refetch()} sx={{ mt: 2 }}>
          {t("s3Explorer.error.retry")}
        </Button>
      </Box>
    );
  };

  const renderLoadingSkeletons = () => {
    return (
      <List sx={{ p: 1 }}>
        {[...Array(8)].map((_, index) => (
          <ListItem key={index} sx={{ borderRadius: "8px", my: 0.5 }}>
            <ListItemIcon>
              <Skeleton variant="circular" width={24} height={24} />
            </ListItemIcon>
            <ListItemText
              primary={<Skeleton variant="text" width="60%" />}
              secondary={<Skeleton variant="text" width="40%" />}
            />
          </ListItem>
        ))}
      </List>
    );
  };

  const renderEmptyState = () => {
    if (debouncedFilter && virtualizedItems.length === 0) {
      return (
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="200px"
          p={3}
        >
          <SearchIcon
            sx={{ fontSize: 48, color: theme.palette.text.secondary, mb: 2 }}
          />
          <Typography variant="body1" color="text.secondary">
            {t("s3Explorer.empty.noResults")}
          </Typography>
        </Box>
      );
    }

    if (virtualizedItems.length === 0) {
      return (
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="200px"
          p={3}
        >
          <FolderIcon
            sx={{ fontSize: 48, color: theme.palette.text.secondary, mb: 2 }}
          />
          <Typography variant="body1" color="text.secondary">
            {t("s3Explorer.empty.folder")}
          </Typography>
        </Box>
      );
    }

    return null;
  };

  const renderVirtualizedItem = (
    item: VirtualizedItem,
    isSelected: boolean,
  ) => {
    const prefix = item.data as string;
    const folderName = prefix.split("/").slice(-2)[0];

    return (
      <ListItem
        onClick={() => handlePathClick(prefix)}
        onMouseEnter={() => handleFolderHover(prefix)}
        onMouseLeave={handleFolderLeave}
        sx={{
          cursor: "pointer",
          borderRadius: "8px",
          my: 0.5,
          backgroundColor: isSelected
            ? alpha(theme.palette.primary.main, 0.08)
            : "transparent",
          "&:hover": {
            backgroundColor: alpha(theme.palette.primary.main, 0.04),
            transform: "scale(1.01)",
          },
          transition: "all 0.2s ease",
        }}
      >
        <ListItemIcon>
          <FolderIcon
            sx={{ color: theme.palette.primary.main, fontSize: 24 }}
          />
        </ListItemIcon>
        <ListItemText
          primary={
            <Typography
              variant="body2"
              sx={{ fontWeight: 500, color: theme.palette.primary.main }}
            >
              {highlightMatch(folderName, debouncedFilter)}
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
    );
  };

  if (isLoading && isInitialLoad) {
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
          {t("s3Explorer.loading.initializing")}
        </Typography>
      </Box>
    );
  }

  if (error) {
    return renderErrorState(error);
  }

  return (
    <Box p={isMobile ? 2 : 3} ref={containerRef}>
      {/* Filter Input */}
      <Box
        mb={2}
        display="flex"
        flexDirection={isMobile ? "column" : "row"}
        gap={2}
        alignItems={isMobile ? "stretch" : "center"}
      >
        <TextField
          label={t("s3Explorer.filter.label")}
          variant="outlined"
          size="small"
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          fullWidth
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: nameFilter && (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => setNameFilter("")}
                    edge="end"
                    aria-label={t("s3Explorer.filter.clear")}
                    title={t("s3Explorer.filter.clear")}
                  >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: "8px",
              backgroundColor: theme.palette.background.paper,
            },
          }}
        />
        {debouncedFilter && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ display: "flex", alignItems: "center", whiteSpace: "nowrap" }}
          >
            {t("s3Explorer.filter.resultsCount", {
              count: virtualizedItems.length,
              total: filteredPrefixes.length,
            })}
          </Typography>
        )}
      </Box>

      {/* Breadcrumbs */}
      <Paper
        elevation={0}
        sx={{
          p: 2,
          mb: 2,
          borderRadius: "12px",
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          overflowX: "auto",
        }}
      >
        <Breadcrumbs
          separator={<NavigateNextIcon fontSize="small" />}
          maxItems={isMobile ? 3 : undefined}
        >
          {breadcrumbItems.map((item, index) => {
            if (item.label === "..." && item.fullPath === null) {
              return (
                <Typography
                  key="ellipsis"
                  color="text.secondary"
                  fontSize={isMobile ? "0.875rem" : "1rem"}
                >
                  ...
                </Typography>
              );
            }

            return (
              <Link
                key={item.fullPath || `root-${index}`}
                component="button"
                onClick={() => handlePathClick(item.fullPath)}
                aria-label={item.ariaLabel}
                sx={{
                  textDecoration: "none",
                  color: theme.palette.primary.main,
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                  fontSize: isMobile ? "0.875rem" : "1rem",
                  "&:hover": {
                    textDecoration: "underline",
                  },
                }}
              >
                {item.isRoot ? (
                  <>
                    {restrictedBasePath ? (
                      <FolderIcon fontSize="small" />
                    ) : (
                      <HomeIcon fontSize="small" />
                    )}
                    {!isMobile &&
                      (restrictedBasePath ? item.label : t("common.root"))}
                  </>
                ) : (
                  item.label
                )}
              </Link>
            );
          })}
        </Breadcrumbs>
      </Paper>

      {/* File/Folder List */}
      <Paper
        elevation={0}
        sx={{
          borderRadius: "12px",
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          backgroundColor: theme.palette.background.paper,
          minHeight: "400px",
        }}
      >
        {isLoading ? (
          renderLoadingSkeletons()
        ) : virtualizedItems.length === 0 ? (
          renderEmptyState()
        ) : (
          <Box
            ref={listContainerRef}
            tabIndex={0}
            sx={{
              height: "500px",
              overflow: "auto",
              outline: "none",
              "&:focus": {
                outline: `2px solid ${alpha(theme.palette.primary.main, 0.2)}`,
              },
            }}
          >
            <List
              sx={{
                p: 1,
                height: `${virtualizer.getTotalSize()}px`,
                position: "relative",
              }}
            >
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const item = virtualizedItems[virtualRow.index];
                const isSelected = virtualRow.index === selectedIndex;

                return (
                  <Box
                    key={virtualRow.key}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    {renderVirtualizedItem(item, isSelected)}
                  </Box>
                );
              })}
            </List>
          </Box>
        )}
      </Paper>

      {/* Load More Button */}
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

      {/* Keyboard Navigation Hint */}
      {!isMobile && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", textAlign: "center", mt: 2 }}
        >
          {t("s3Explorer.keyboard.navigation")}
        </Typography>
      )}
    </Box>
  );
};
