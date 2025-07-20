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
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import {
  Storage as StorageIcon,
  Folder as FolderIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
  ChevronLeft,
  ChevronRight,
} from "@mui/icons-material";
import { S3Explorer } from "../features/home/S3Explorer";
import AssetExplorer from "../features/assets/AssetExplorer";
import { useGetConnectors } from "../api/hooks/useConnectors";

const DRAWER_WIDTH = 280;
const COLLAPSED_DRAWER_WIDTH = 60; // Wider collapsed width to avoid overlap

const AssetsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [selectedConnector, setSelectedConnector] = useState<string | null>(
    null,
  );
  const [filterText, setFilterText] = useState("");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { data: connectorsResponse, isLoading } = useGetConnectors();

  const connectors = connectorsResponse?.data.connectors || [];

  // For debugging
  console.log("AssetsPage connectors:", connectors);
  console.log("Selected connector:", selectedConnector);
  console.log(
    "Selected bucket:",
    selectedConnector
      ? connectors.find((c) => c.id === selectedConnector)?.storageIdentifier
      : null,
  );

  // Filter connectors based on search text
  const filteredConnectors = connectors.filter(
    (connector) =>
      connector.name.toLowerCase().includes(filterText.toLowerCase()) ||
      connector.type.toLowerCase().includes(filterText.toLowerCase()),
  );

  const handleClearFilter = () => {
    setFilterText("");
  };

  const toggleDrawer = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        px: 4,
        pt: 0, // No top padding
        mt: -1.5, // Slightly more negative margin to pull everything up
      }}
    >
      {/* Assets title in blue - styled like Results in SearchPage */}
      <Box sx={{ mb: 0.75 }}>
        {" "}
        {/* Slightly reduced margin */}
        <Typography
          variant="h4"
          component="h1"
          sx={{
            fontWeight: 700,
            mb: 0, // No bottom margin
            background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
            backgroundClip: "text",
            WebkitBackgroundClip: "text",
            color: "transparent",
          }}
        >
          {t("assetsPage.title")}
        </Typography>
      </Box>

      {/* Main content area with sidebar and content */}
      <Box
        sx={{
          display: "flex",
          flexGrow: 1,
          height: "calc(100% - 28px)", // Slightly adjusted height
          position: "relative", // Added for proper positioning
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
            transition: theme.transitions.create(
              ["width", "margin", "min-width"],
              {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              },
            ),
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
              boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px solid",
              borderColor: "divider",
              zIndex: 1200, // Much higher z-index to ensure visibility
              padding: 0,
              "&:hover": {
                bgcolor: "background.paper",
                boxShadow: "0px 6px 12px rgba(0, 0, 0, 0.2)",
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
              <Box sx={{ p: 1.5, pb: 1 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    mb: 1,
                  }}
                >
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {t("assetsPage.connectors")}
                  </Typography>
                </Box>

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
                          onClick={() => setSelectedConnector(connector.id)}
                          sx={{
                            py: 0.75, // Reduced vertical padding
                            borderRadius: 1,
                            mx: 1,
                            "&.Mui-selected": {
                              backgroundColor: alpha(
                                theme.palette.primary.main,
                                0.1,
                              ),
                              "&:hover": {
                                backgroundColor: alpha(
                                  theme.palette.primary.main,
                                  0.15,
                                ),
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
                                  bgcolor: alpha(
                                    theme.palette.primary.main,
                                    0.15,
                                  ),
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
                              fontWeight:
                                selectedConnector === connector.id ? 600 : 400,
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
          {selectedConnector ? (
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
                bucketName={
                  connectors.find((c) => c.id === selectedConnector)
                    ?.storageIdentifier
                }
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
    </Box>
  );
};

export default AssetsPage;
