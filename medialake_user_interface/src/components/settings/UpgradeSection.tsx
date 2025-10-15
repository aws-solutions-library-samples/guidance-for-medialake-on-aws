/**
 * System Upgrade Section Component
 * Displays current version, available versions, and upgrade controls
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
  CircularProgress,
  Alert,
  LinearProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
  useTheme,
  Tabs,
  Tab,
} from "@mui/material";
import {
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  CloudUpload as CloudUploadIcon,
  History as HistoryIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import {
  getVersions,
  getUpgradeStatus,
  triggerUpgrade,
  type Version,
  type UpgradeStatusResponse,
} from "@/api/updatesService";
import { UpgradeHistoryView } from "@/components/settings/UpgradeHistoryView";

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div role="tabpanel" hidden={value !== index}>
    {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
  </div>
);

export const UpgradeSection: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  console.log("🔧 UpgradeSection component mounted");

  const [tabValue, setTabValue] = useState(0);
  const [status, setStatus] = useState<UpgradeStatusResponse | null>(null);
  const [versions, setVersions] = useState<{
    branches: Version[];
    tags: Version[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [upgrading, setUpgrading] = useState(false);

  // Poll for status updates when upgrade is in progress
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (status?.upgrade_status === "in_progress") {
      interval = setInterval(() => {
        fetchStatus();
      }, 5000); // Poll every 5 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [status?.upgrade_status]);

  const fetchStatus = async () => {
    try {
      console.log("🔧 Calling getUpgradeStatus API...");
      const statusData = await getUpgradeStatus();
      console.log("🔧 Status data received:", statusData);
      setStatus(statusData);
    } catch (err) {
      console.error("🔧 Failed to fetch status:", err);
      throw err;
    }
  };

  const fetchVersions = async () => {
    try {
      console.log("🔧 Calling getVersions API...");
      const versionsData = await getVersions();
      console.log("🔧 Versions data received:", versionsData);
      console.log("🔧 Versions data type:", typeof versionsData);
      console.log("🔧 Versions data keys:", Object.keys(versionsData || {}));
      console.log("🔧 Branches:", versionsData?.branches);
      console.log("🔧 Tags:", versionsData?.tags);

      if (versionsData && versionsData.branches && versionsData.tags) {
        setVersions({
          branches: versionsData.branches,
          tags: versionsData.tags,
        });
        console.log("🔧 ✓ Versions state updated successfully");
      } else {
        console.error("🔧 ✗ Invalid versions data structure:", versionsData);
        throw new Error("Invalid versions data structure");
      }
    } catch (err) {
      console.error("🔧 Failed to fetch versions:", err);
      throw err;
    }
  };

  const loadData = async () => {
    console.log("🔧 loadData called");
    setLoading(true);
    setError(null);

    try {
      console.log("🔧 Fetching status and versions...");
      await Promise.all([fetchStatus(), fetchVersions()]);
      console.log("🔧 Data loaded successfully");
    } catch (err: any) {
      console.error("🔧 Error loading data:", err);
      setError(err.message || "Failed to load upgrade information");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleVersionSelect = (version: Version) => {
    setSelectedVersion(version);
    setConfirmDialogOpen(true);
  };

  const handleConfirmUpgrade = async () => {
    if (!selectedVersion) return;

    setUpgrading(true);
    setConfirmDialogOpen(false);

    try {
      await triggerUpgrade({
        target_version: selectedVersion.name,
        version_type: selectedVersion.type,
        confirm_upgrade: true,
      });

      // Refresh status after triggering
      await fetchStatus();
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message || "Failed to trigger upgrade",
      );
    } finally {
      setUpgrading(false);
      setSelectedVersion(null);
    }
  };

  const handleCancelUpgrade = () => {
    setConfirmDialogOpen(false);
    setSelectedVersion(null);
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        {t("settings.systemSettings.upgrade.title", "System Upgrades")}
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        {t(
          "settings.systemSettings.upgrade.description",
          "Manage MediaLake system upgrades and view version history.",
        )}
      </Typography>

      <Divider sx={{ my: 3 }} />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Current Version & Status */}
      <Card
        elevation={0}
        sx={{
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
          mb: 3,
        }}
      >
        <CardContent>
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 2,
            }}
          >
            <Typography variant="h6">
              {t(
                "settings.systemSettings.upgrade.currentVersion",
                "Current Version",
              )}
            </Typography>
            <Button
              startIcon={<RefreshIcon />}
              onClick={loadData}
              disabled={status?.upgrade_status === "in_progress"}
            >
              {t("common.refresh", "Refresh")}
            </Button>
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
            <Typography variant="h5" sx={{ fontFamily: "monospace" }}>
              {status?.current_version || "unknown"}
            </Typography>
            <Chip
              label={status?.upgrade_status || "idle"}
              color={
                status?.upgrade_status === "in_progress"
                  ? "warning"
                  : status?.upgrade_status === "failed"
                    ? "error"
                    : "success"
              }
              size="small"
            />
          </Box>

          {status?.active_upgrade && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(
                  "settings.systemSettings.upgrade.upgradingTo",
                  "Upgrading to {{version}}",
                  { version: status.active_upgrade.target_version },
                )}
              </Typography>
              <Box
                sx={{ display: "flex", alignItems: "center", gap: 2, mt: 1 }}
              >
                <LinearProgress
                  variant="determinate"
                  value={status.active_upgrade.progress.percentage}
                  sx={{ flex: 1, height: 8, borderRadius: 4 }}
                />
                <Typography variant="body2" sx={{ minWidth: 50 }}>
                  {status.active_upgrade.progress.percentage}%
                </Typography>
              </Box>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 1, display: "block" }}
              >
                {status.active_upgrade.progress.stage}:{" "}
                {status.active_upgrade.progress.current_action}
              </Typography>
            </Box>
          )}

          {status?.last_upgrade && !status.active_upgrade && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                bgcolor: "background.default",
                borderRadius: 1,
              }}
            >
              <Typography variant="caption" color="text.secondary">
                {t(
                  "settings.systemSettings.upgrade.lastUpgrade",
                  "Last upgrade",
                )}
                : {status.last_upgrade.version} -{" "}
                {new Date(status.last_upgrade.timestamp).toLocaleString()}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Tabs for Versions and History */}
      <Card
        elevation={0}
        sx={{
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 2,
        }}
      >
        <Tabs
          value={tabValue}
          onChange={(_, newValue) => setTabValue(newValue)}
          sx={{ borderBottom: `1px solid ${theme.palette.divider}`, px: 2 }}
        >
          <Tab
            icon={<CloudUploadIcon />}
            iconPosition="start"
            label={t(
              "settings.systemSettings.upgrade.availableVersions",
              "Available Versions",
            )}
          />
          <Tab
            icon={<HistoryIcon />}
            iconPosition="start"
            label={t("settings.systemSettings.upgrade.history", "History")}
          />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <CardContent>
            {versions && versions.branches && versions.tags ? (
              <Box>
                {/* Tags */}
                <Typography
                  variant="subtitle1"
                  gutterBottom
                  sx={{ fontWeight: 600 }}
                >
                  {t("settings.systemSettings.upgrade.tags", "Release Tags")}
                </Typography>
                <List>
                  {versions.tags.length > 0 ? (
                    versions.tags.slice(0, 10).map((version) => (
                      <ListItem key={version.sha} disablePadding>
                        <ListItemButton
                          onClick={() => handleVersionSelect(version)}
                          disabled={
                            status?.upgrade_status === "in_progress" ||
                            version.name === status?.current_version ||
                            upgrading
                          }
                        >
                          <ListItemText
                            primary={
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography sx={{ fontFamily: "monospace" }}>
                                  {version.name}
                                </Typography>
                                {version.is_latest && (
                                  <Chip
                                    label="Latest"
                                    size="small"
                                    color="primary"
                                  />
                                )}
                                {version.name === status?.current_version && (
                                  <Chip
                                    label="Current"
                                    size="small"
                                    color="success"
                                  />
                                )}
                              </Box>
                            }
                            secondary={
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {new Date(version.date).toLocaleDateString()} -{" "}
                                {version.message}
                              </Typography>
                            }
                          />
                        </ListItemButton>
                      </ListItem>
                    ))
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ p: 2 }}
                    >
                      {t(
                        "settings.systemSettings.upgrade.noTags",
                        "No release tags available",
                      )}
                    </Typography>
                  )}
                </List>

                <Divider sx={{ my: 2 }} />

                {/* Branches */}
                <Typography
                  variant="subtitle1"
                  gutterBottom
                  sx={{ fontWeight: 600 }}
                >
                  {t("settings.systemSettings.upgrade.branches", "Branches")}
                </Typography>
                <List>
                  {versions.branches.length > 0 ? (
                    versions.branches.map((version) => (
                      <ListItem key={version.sha} disablePadding>
                        <ListItemButton
                          onClick={() => handleVersionSelect(version)}
                          disabled={
                            status?.upgrade_status === "in_progress" ||
                            version.name === status?.current_version ||
                            upgrading
                          }
                        >
                          <ListItemText
                            primary={
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography sx={{ fontFamily: "monospace" }}>
                                  {version.name}
                                </Typography>
                                {version.is_default && (
                                  <Chip
                                    label="Default"
                                    size="small"
                                    color="info"
                                  />
                                )}
                                {version.name === status?.current_version && (
                                  <Chip
                                    label="Current"
                                    size="small"
                                    color="success"
                                  />
                                )}
                              </Box>
                            }
                            secondary={
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {new Date(version.date).toLocaleDateString()} -{" "}
                                {version.message}
                              </Typography>
                            }
                          />
                        </ListItemButton>
                      </ListItem>
                    ))
                  ) : (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ p: 2 }}
                    >
                      {t(
                        "settings.systemSettings.upgrade.noBranches",
                        "No branches available",
                      )}
                    </Typography>
                  )}
                </List>
              </Box>
            ) : (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ p: 2, textAlign: "center" }}
              >
                {t(
                  "settings.systemSettings.upgrade.loadingVersions",
                  "Loading available versions...",
                )}
              </Typography>
            )}
          </CardContent>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <UpgradeHistoryView />
        </TabPanel>
      </Card>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={handleCancelUpgrade}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {t("settings.systemSettings.upgrade.confirmTitle", "Confirm Upgrade")}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t(
              "settings.systemSettings.upgrade.confirmMessage",
              "Are you sure you want to upgrade to {{version}}? This will trigger a deployment pipeline and may cause temporary service interruption.",
              { version: selectedVersion?.name },
            )}
          </DialogContentText>
          <Alert severity="warning" sx={{ mt: 2 }}>
            {t(
              "settings.systemSettings.upgrade.confirmWarning",
              "This action cannot be undone. The upgrade process typically takes 15-20 minutes.",
            )}
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelUpgrade}>
            {t("common.cancel", "Cancel")}
          </Button>
          <Button
            onClick={handleConfirmUpgrade}
            variant="contained"
            color="primary"
            startIcon={
              upgrading ? <CircularProgress size={16} /> : <CloudUploadIcon />
            }
            disabled={upgrading}
          >
            {upgrading
              ? t("settings.systemSettings.upgrade.upgrading", "Upgrading...")
              : t("settings.systemSettings.upgrade.confirm", "Confirm Upgrade")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
