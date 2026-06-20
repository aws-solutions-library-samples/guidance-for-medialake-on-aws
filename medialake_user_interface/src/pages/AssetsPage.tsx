import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Paper,
  useTheme,
  alpha,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Divider,
  CircularProgress,
  TextField,
  InputAdornment,
  IconButton,
  Button,
  Chip,
} from "@mui/material";
import {
  Storage as StorageIcon,
  Folder as FolderIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ChevronLeft,
  ChevronRight,
  Person as PersonIcon,
  CloudUpload as CloudUploadIcon,
} from "@mui/icons-material";
import { PageHeader, PageContent } from "@/components/common/layout";
import { springEasing } from "@/constants";
import { zIndexTokens } from "@/theme/tokens";
import AssetExplorer from "../features/assets/AssetExplorer";
import { useSearchConnectors } from "../api/hooks/useSearchConnectors";
import { useMyAssetsConnector } from "../api/hooks/useMyAssetsConnector";
import { S3UploaderModal } from "../features/upload";
import { usePermission } from "@/permissions";
import { useFeatureFlag } from "@/contexts/FeatureFlagsContext";

const DRAWER_WIDTH = 280;
const COLLAPSED_DRAWER_WIDTH = 60; // Wider collapsed width to avoid overlap

const AssetsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null);
  const [selectedIsMyAssets, setSelectedIsMyAssets] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [filterText, setFilterText] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { data: connectorsResponse, isLoading } = useSearchConnectors();
  const { connector: myAssetsConnector, isLoading: isMyAssetsLoading } = useMyAssetsConnector();

  // Feature flag — gate the My Assets section (default off).
  const myAssetsEnabled = useFeatureFlag("my-assets-enabled", false);

  // Only users with upload permission see the upload entry point.
  const { can } = usePermission();
  const canUpload = can("upload", "asset");

  const connectors = connectorsResponse?.data.connectors || [];

  // For debugging

  // Filter connectors based on search text
  const filteredConnectors = connectors.filter(
    (connector) =>
      connector.name.toLowerCase().includes(filterText.toLowerCase()) ||
      connector.type.toLowerCase().includes(filterText.toLowerCase())
  );

  const handleClearFilter = () => {
    setFilterText("");
  };

  const toggleDrawer = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader
        title={t("assetsPage.title", "Assets")}
        description={t(
          "assetsPage.description",
          "Browse and manage your media assets from connected storage"
        )}
      />

      <PageContent isLoading={isLoading} error={null}>
        <Box
          sx={{
            display: "flex",
            flexGrow: 1,
            height: "100%",
            position: "relative",
          }}
        >
          {/* Left Panel - Connectors List with white background */}
          <Box
            sx={{
              width: isCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
              minWidth: isCollapsed ? COLLAPSED_DRAWER_WIDTH : DRAWER_WIDTH,
              mr: 3, // Consistent margin
              height: "100%",
              display: "flex",
              flexDirection: "column",
              backgroundColor: "background.paper",
              borderRadius: 2,
              transition: `width ${theme.transitions.duration.enteringScreen}ms ${springEasing}, margin ${theme.transitions.duration.enteringScreen}ms ${springEasing}, min-width ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
              overflow: "visible", // Allow button to be visible outside
              position: "relative",
              zIndex: 1,
            }}
          >
            {/* Collapse/Expand Button */}
            <Button
              onClick={toggleDrawer}
              sx={{
                position: "absolute",
                right: -16,
                top: "50%",
                transform: "translateY(-50%)",
                minWidth: "32px",
                width: "32px",
                height: "32px",
                bgcolor: "background.paper",
                borderRadius: "8px",
                boxShadow: `0 4px 8px ${alpha(theme.palette.common.black, 0.12)}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "1px solid",
                borderColor: "divider",
                zIndex: zIndexTokens.sidebar, // Much higher z-index to ensure visibility
                padding: 0,
                "&:hover": {
                  bgcolor: "background.paper",
                  boxShadow: `0 6px 12px ${alpha(theme.palette.common.black, 0.16)}`,
                },
              }}
            >
              {isCollapsed ? (
                <ChevronRight sx={{ fontSize: 20 }} />
              ) : (
                <ChevronLeft sx={{ fontSize: 20 }} />
              )}
            </Button>

            {isCollapsed ? (
              // Collapsed view - show only the icon, centered
              <Box
                sx={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  // Shift icon to the left to avoid overlap with button
                  pl: 0,
                  pr: 2,
                }}
              >
                <StorageIcon
                  sx={{
                    color: theme.palette.primary.main,
                    fontSize: 24,
                  }}
                />
              </Box>
            ) : (
              // Expanded view - show full content
              <>
                {myAssetsEnabled && (
                  <>
                    {/* My Assets pinned item */}
                    <Box sx={{ p: 1 }}>
                      <ListItemButton
                        selected={selectedIsMyAssets}
                        onClick={() => {
                          setSelectedIsMyAssets(true);
                          setSelectedConnector(null);
                        }}
                        sx={{
                          borderRadius: 1,
                          borderLeft: `3px solid ${theme.palette.primary.main}`,
                          backgroundColor: selectedIsMyAssets
                            ? alpha(theme.palette.primary.main, 0.08)
                            : alpha(theme.palette.primary.main, 0.04),
                          "&.Mui-selected": {
                            backgroundColor: alpha(theme.palette.primary.main, 0.08),
                            "&:hover": {
                              backgroundColor: alpha(theme.palette.primary.main, 0.12),
                            },
                          },
                        }}
                      >
                        <ListItemIcon sx={{ minWidth: 36 }}>
                          <PersonIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={t("assetsPage.myAssets")}
                          primaryTypographyProps={{
                            fontWeight: selectedIsMyAssets ? 600 : 400,
                            color: selectedIsMyAssets
                              ? theme.palette.primary.main
                              : theme.palette.text.primary,
                            variant: "body2",
                          }}
                        />
                        {isMyAssetsLoading ? (
                          <CircularProgress size={16} />
                        ) : (
                          <Chip label="Personal" size="small" color="primary" variant="outlined" />
                        )}
                      </ListItemButton>
                    </Box>

                    <Divider />
                  </>
                )}
                <Box sx={{ p: 1.5, pb: 1 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Connectors
                  </Typography>

                  {/* More compact search field */}
                  <TextField
                    fullWidth
                    size="small"
                    placeholder={t("common.search")}
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    sx={{
                      mb: 1,
                      width: "90%", // Slightly smaller width
                      mx: "auto", // Center it
                      "& .MuiInputBase-root": {
                        height: 32, // Smaller height
                        fontSize: "0.875rem", // Smaller font
                      },
                      "& .MuiInputBase-input": {
                        py: 0.5, // Reduced padding
                      },
                    }}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon fontSize="small" sx={{ fontSize: 18 }} />
                        </InputAdornment>
                      ),
                      endAdornment: filterText ? (
                        <InputAdornment position="end">
                          <IconButton
                            size="small"
                            onClick={handleClearFilter}
                            edge="end"
                            sx={{ p: 0.5 }}
                          >
                            <ClearIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        </InputAdornment>
                      ) : null,
                    }}
                  />
                </Box>
                <Divider />
                <Box sx={{ flexGrow: 1, overflow: "auto" }}>
                  {isLoading ? (
                    <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
                      <CircularProgress size={24} />
                    </Box>
                  ) : filteredConnectors.length === 0 ? (
                    <Box sx={{ p: 2, textAlign: "center" }}>
                      <Typography variant="body2" color="text.secondary">
                        {t("common.noResults")}
                      </Typography>
                    </Box>
                  ) : (
                    <List dense disablePadding>
                      {filteredConnectors.map((connector) => (
                        <ListItem key={connector.id} disablePadding>
                          <ListItemButton
                            selected={selectedConnector === connector.id}
                            onClick={() => {
                              setSelectedConnector(connector.id);
                              setSelectedIsMyAssets(false);
                            }}
                            sx={{
                              py: 0.75, // Reduced vertical padding
                              borderRadius: 1,
                              mx: 1,
                              "&.Mui-selected": {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                "&:hover": {
                                  backgroundColor: alpha(theme.palette.primary.main, 0.15),
                                },
                              },
                            }}
                          >
                            <ListItemIcon sx={{ minWidth: 36 }}>
                              {selectedConnector === connector.id ? (
                                <Box
                                  sx={{
                                    width: 24,
                                    height: 24,
                                    borderRadius: "50%",
                                    bgcolor: alpha(theme.palette.primary.main, 0.15),
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                  }}
                                >
                                  <Box
                                    component="span"
                                    sx={{
                                      width: 16,
                                      height: 16,
                                      borderRadius: "50%",
                                      bgcolor: theme.palette.primary.main,
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                    }}
                                  >
                                    <Box
                                      component="span"
                                      sx={{
                                        color: "white",
                                        fontSize: 14,
                                        fontWeight: "bold",
                                        lineHeight: 1,
                                        mt: "-2px", // Fine-tune vertical alignment
                                      }}
                                    >
                                      ✓
                                    </Box>
                                  </Box>
                                </Box>
                              ) : (
                                <StorageIcon
                                  fontSize="small"
                                  sx={{
                                    color: theme.palette.text.secondary,
                                  }}
                                />
                              )}
                            </ListItemIcon>
                            <ListItemText
                              primary={connector.name}
                              secondary={connector.type.toUpperCase()}
                              primaryTypographyProps={{
                                fontWeight: selectedConnector === connector.id ? 600 : 400,
                                color:
                                  selectedConnector === connector.id
                                    ? theme.palette.primary.main
                                    : theme.palette.text.primary,
                                variant: "body2", // Smaller text
                              }}
                              secondaryTypographyProps={{
                                variant: "caption", // Even smaller text for the secondary line
                              }}
                            />
                          </ListItemButton>
                        </ListItem>
                      ))}
                    </List>
                  )}
                </Box>
              </>
            )}
          </Box>

          {/* Main Content Area */}
          <Box
            sx={{
              flexGrow: 1,
              height: "100%",
              overflow: "auto",
              backgroundColor: alpha(theme.palette.background.default, 0.5),
            }}
          >
            {selectedIsMyAssets && myAssetsEnabled ? (
              <Paper
                elevation={0}
                sx={{
                  height: "100%",
                  borderRadius: "12px",
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                  backgroundColor: theme.palette.background.paper,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {/* Header */}
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    p: 2,
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <PersonIcon color="primary" />
                    <Typography variant="h6">{t("assetsPage.myAssets")}</Typography>
                    <Chip label="Personal · Private" size="small" />
                  </Box>
                  {canUpload && (
                    <Button
                      variant="contained"
                      startIcon={<CloudUploadIcon />}
                      onClick={() => setIsUploadModalOpen(true)}
                      disabled={!myAssetsConnector}
                    >
                      Upload
                    </Button>
                  )}
                </Box>

                {/* Asset grid — scoped to personal prefix */}
                <Box sx={{ flex: 1, overflow: "auto" }}>
                  {myAssetsConnector ? (
                    <AssetExplorer
                      connectorId={myAssetsConnector.id}
                      bucketName={myAssetsConnector.storageIdentifier}
                      objectPrefix={myAssetsConnector.objectPrefix}
                      emptyStateContent={
                        <Box
                          sx={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            height: "100%",
                            p: 4,
                          }}
                        >
                          <CloudUploadIcon
                            sx={{ fontSize: 64, color: "text.secondary", opacity: 0.5, mb: 2 }}
                          />
                          <Typography variant="h6" color="text.secondary" gutterBottom>
                            {t("assetsPage.myAssetsEmpty.title", "No personal assets yet")}
                          </Typography>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ mb: 3, textAlign: "center", maxWidth: 400 }}
                          >
                            {t(
                              "assetsPage.myAssetsEmpty.description",
                              "Upload your first file to My Assets"
                            )}
                          </Typography>
                          <Button
                            variant="contained"
                            startIcon={<CloudUploadIcon />}
                            onClick={() => setIsUploadModalOpen(true)}
                          >
                            {t("assetsPage.myAssetsEmpty.uploadCta", "Upload to My Assets")}
                          </Button>
                        </Box>
                      }
                    />
                  ) : isMyAssetsLoading ? (
                    <Box
                      sx={{
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center",
                        height: "100%",
                      }}
                    >
                      <CircularProgress />
                    </Box>
                  ) : null}
                </Box>
              </Paper>
            ) : selectedConnector ? (
              <Paper
                elevation={0}
                sx={{
                  height: "100%",
                  borderRadius: "12px",
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                  backgroundColor: theme.palette.background.paper,
                  overflow: "hidden",
                }}
              >
                <AssetExplorer
                  connectorId={selectedConnector}
                  bucketName={connectors.find((c) => c.id === selectedConnector)?.storageIdentifier}
                />
              </Paper>
            ) : (
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  borderRadius: "12px",
                  border: `1px dashed ${alpha(theme.palette.divider, 0.3)}`,
                  backgroundColor: alpha(theme.palette.background.paper, 0.5),
                }}
              >
                <FolderIcon
                  sx={{
                    fontSize: 64,
                    color: alpha(theme.palette.text.secondary, 0.5),
                    mb: 2,
                  }}
                />
                <Typography variant="h6" color="text.secondary">
                  {t("assetsPage.selectConnector")}
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      </PageContent>

      {/* Upload modal for My Assets context */}
      <S3UploaderModal
        open={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        defaultConnectorId={myAssetsConnector?.id}
        lockConnector={true}
        title={t("assetsPage.uploadToMyAssets")}
        defaultObjectPrefix={myAssetsConnector?.objectPrefix}
      />
    </Box>
  );
};

export default AssetsPage;
