import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  IconButton,
  Badge,
  Button,
  Popover,
  Box,
  Stack,
  Typography,
  Paper,
  Tooltip,
  LinearProgress,
} from "@mui/material";
import {
  Notifications as NotificationsIcon,
  Close as CloseIcon,
  Download as DownloadIcon,
} from "@mui/icons-material";
import { DownloadLinksDisplay } from "./DownloadLinksDisplay";
import { DismissConfirmationDialog } from "./DismissConfirmationDialog";
import { useDeleteBulkDownloadJob } from "@/api/hooks/useAssets";
import { useJobNotifications } from "@/hooks/useJobNotifications";

// Helper function to format file sizes
const formatFileSize = (bytes: string | number): string => {
  const numBytes = typeof bytes === "string" ? parseInt(bytes, 10) : bytes;
  if (isNaN(numBytes)) return "Unknown size";

  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = numBytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

// Helper function to format dates
const formatDate = (dateString: string): string => {
  if (!dateString) return "Unknown";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString("en-US", {
    timeZone: "America/Los_Angeles",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
};

// Helper function to get icon color for job status
const getStatusIconColor = (jobStatus?: string) => {
  switch (jobStatus) {
    case "INITIATED":
      return "#1976d2"; // Blue
    case "ASSESSED":
      return "#1976d2"; // Orange
    case "STAGING":
      return "#1976d2"; // Purple
    case "PROCESSING":
      return "#1976d2"; // Blue
    case "COMPLETED":
      return "#2e7d32"; // Green
    case "FAILED":
      return "#d32f2f"; // Red
    default:
      return "#757575"; // Gray
  }
};

/**
 * Supported notification behaviour:
 * - **sticky**               : permanent, no dismiss option.
 * - **sticky-dismissible**   : sticky until the user clicks a `Dismiss` button.
 * - **dismissible**          : shows an "X" button and (optionally) auto–closes after a timeout.
 */
export type NotificationType = "sticky" | "sticky-dismissible" | "dismissible";

export interface Notification {
  id: string;
  message: string;
  /** Behaviour preset (default: `dismissible`). */
  type?: NotificationType;
  /** Marks whether the notification has been opened in the panel. */
  seen?: boolean;
  /**
   * CTA button label (e.g. "Open", "Retry").
   * Shown left‑most when provided.
   */
  actionText?: string;
  /** Click handler for the CTA button. */
  onAction?: () => void;
  /** Auto‑close delay (ms) for `dismissible` notifications. */
  autoCloseMs?: number;
  /** Job ID for tracking backend jobs */
  jobId?: string;
  /** Current job status */
  jobStatus?:
    | "INITIATED"
    | "ASSESSED"
    | "STAGING"
    | "PROCESSING"
    | "COMPLETED"
    | "FAILED";
  /** Download URLs for completed jobs */
  downloadUrls?:
    | {
        zippedFiles?: string;
        files?: string[];
        singleFiles?: string[];
      }
    | string[];
  /** Job creation timestamp */
  createdAt?: string;
  /** Job last updated timestamp */
  updatedAt?: string;
  /** Download expiration timestamp */
  expiresAt?: string;
  /** Download expiration in seconds */
  expiresIn?: string;
  /** Job progress percentage (0-100) */
  progress?: number;
  /** Total size of all files in bytes */
  totalSize?: string | number;
  /** Total number of assets found */
  foundAssetsCount?: number;
  /** Number of zipped files */
  smallFilesCount?: number;
  /** Number of files */
  largeFilesCount?: number;
}

// ──────────────────────────\
//  Context & provider hook
// ──────────────────────────/
interface NotificationContextValue {
  notifications: Notification[];
  add: (n: Omit<Notification, "id" | "seen">) => string;
  markAsSeen: (id: string) => void;
  dismiss: (id: string) => void;
  update: (id: string, updates: Partial<Omit<Notification, "id">>) => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(
  null,
);

export const useNotifications = (): NotificationContextValue => {
  const ctx = useContext(NotificationContext);
  if (!ctx)
    throw new Error("useNotifications must be inside <NotificationProvider>");
  return ctx;
};

const STORAGE_KEY = "medialake_notifications";

export const NotificationProvider: React.FC<React.PropsWithChildren> = ({
  children,
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Load notifications from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsedNotifications = JSON.parse(saved) as Notification[];
        // Filter out expired notifications
        const now = Date.now();
        const validNotifications = parsedNotifications.filter((n) => {
          if (n.expiresAt) {
            return new Date(n.expiresAt).getTime() > now;
          }
          return true;
        });
        setNotifications(validNotifications);
      }
    } catch (error) {
      console.error("Error loading notifications from localStorage:", error);
    }
  }, []);

  // Save notifications to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications));
    } catch (error) {
      console.error("Error saving notifications to localStorage:", error);
    }
  }, [notifications]);

  const add = useCallback((n: Omit<Notification, "id" | "seen">) => {
    const id = crypto.randomUUID();
    setNotifications((prev) => [...prev, { id, seen: false, ...n }]);
    return id;
  }, []);

  const markAsSeen = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, seen: true } : n)),
    );
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const update = useCallback(
    (id: string, updates: Partial<Omit<Notification, "id">>) => {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, ...updates } : n)),
      );
    },
    [],
  );

  // Auto‑close for dismissible notifications
  useEffect(() => {
    const timers = notifications
      .filter((n) => n.type === "dismissible" && n.autoCloseMs)
      .map((n) => setTimeout(() => dismiss(n.id), n.autoCloseMs));

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [notifications, dismiss]);

  return (
    <NotificationContext.Provider
      value={{ notifications, add, markAsSeen, dismiss, update }}
    >
      {children}
    </NotificationContext.Provider>
  );
};

// ──────────────────────────\
//  Bell icon + dropdown UI
// ──────────────────────────/
export const NotificationCenter: React.FC = () => {
  const { notifications, markAsSeen, dismiss } = useNotifications();
  const { dismissJobNotification, clearAllJobNotifications } =
    useJobNotifications();
  const deleteBulkDownloadJob = useDeleteBulkDownloadJob();

  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [dismissDialog, setDismissDialog] = useState<{
    open: boolean;
    notificationId: string;
    message: string;
  }>({ open: false, notificationId: "", message: "" });

  const open = Boolean(anchorEl);

  // Calculate unseen count based on localStorage tracking
  const getUnseenCount = (): number => {
    try {
      const unseen = localStorage.getItem("medialake_unseen_notifications");
      const unseenIds = new Set(unseen ? JSON.parse(unseen) : []);
      return notifications.filter((n) => unseenIds.has(n.id)).length;
    } catch {
      return 0;
    }
  };

  // Calculate active jobs count (not COMPLETED or FAILED)
  const getActiveJobsCount = (): number => {
    return notifications.filter(
      (n) =>
        n.jobStatus && n.jobStatus !== "COMPLETED" && n.jobStatus !== "FAILED",
    ).length;
  };

  const [unseenCount, setUnseenCount] = useState(getUnseenCount());
  const [activeJobsCount, setActiveJobsCount] = useState(getActiveJobsCount());

  // Update counts when notifications change
  useEffect(() => {
    setUnseenCount(getUnseenCount());
    setActiveJobsCount(getActiveJobsCount());
  }, [notifications]);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
    // Mark all notifications as seen
    markAllNotificationsAsSeen();
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const markAllNotificationsAsSeen = () => {
    // Clear unseen notifications from localStorage
    localStorage.removeItem("medialake_unseen_notifications");
    setUnseenCount(0);

    // Mark all job notifications as seen in job tracking
    notifications.forEach((n) => {
      if (n.jobId && n.jobStatus) {
        // Mark this job+status combination as seen
        const seenJobs = getSeenJobNotifications();
        const jobKey = `${n.jobId}:${n.jobStatus}`;
        seenJobs.add(jobKey);
        localStorage.setItem(
          "medialake_seen_job_notifications",
          JSON.stringify([...seenJobs]),
        );
      }
      if (!n.seen) markAsSeen(n.id);
    });
  };

  // Helper function to get seen job notifications
  const getSeenJobNotifications = (): Set<string> => {
    try {
      const seen = localStorage.getItem("medialake_seen_job_notifications");
      return new Set(seen ? JSON.parse(seen) : []);
    } catch {
      return new Set();
    }
  };

  // Helper function to determine which dismiss function to use
  const dismissNotification = (notificationId: string) => {
    const notification = notifications.find((n) => n.id === notificationId);
    if (notification?.jobId) {
      // Use custom dismiss for job notifications
      dismissJobNotification(notificationId);
    } else {
      // Use regular dismiss for non-job notifications
      dismiss(notificationId);
    }
  };

  const handleDismissClick = (notification: Notification) => {
    if (
      notification.type === "sticky-dismissible" &&
      notification.jobStatus === "COMPLETED"
    ) {
      // Show confirmation dialog for completed downloads
      setDismissDialog({
        open: true,
        notificationId: notification.id,
        message: notification.message,
      });
    } else {
      // Direct dismiss for other notifications
      dismissNotification(notification.id);
    }
  };

  const handleConfirmDismiss = async () => {
    // Find the notification to get the jobId
    const notification = notifications.find(
      (n) => n.id === dismissDialog.notificationId,
    );

    // Dismiss the notification from UI first
    dismissNotification(dismissDialog.notificationId);
    setDismissDialog({ open: false, notificationId: "", message: "" });

    // Delete the job from database if it has a jobId
    if (notification?.jobId) {
      try {
        await deleteBulkDownloadJob.mutateAsync(notification.jobId);
      } catch (error) {
        console.error("Failed to delete bulk download job:", error);
        // Note: We don't show an error to the user since the notification is already dismissed
        // and the job will eventually be cleaned up by the backend
      }
    }
  };

  const handleCancelDismiss = () => {
    setDismissDialog({ open: false, notificationId: "", message: "" });
  };

  return (
    <>
      <Tooltip
        title={
          unseenCount > 0
            ? `${unseenCount} New`
            : activeJobsCount > 0
              ? `${activeJobsCount} Running`
              : "No notifications"
        }
        arrow
      >
        <IconButton
          aria-label="notifications"
          onClick={handleClick}
          sx={{ position: "relative" }}
        >
          <Badge
            badgeContent={
              unseenCount > 0
                ? unseenCount
                : activeJobsCount > 0
                  ? activeJobsCount
                  : undefined
            }
            color={unseenCount > 0 ? "error" : "success"}
            sx={{
              "& .MuiBadge-badge": {
                fontSize: "0.75rem",
                height: 16,
                minWidth: 16,
              },
            }}
          >
            <NotificationsIcon />
          </Badge>
        </IconButton>
      </Tooltip>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "right",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "right",
        }}
      >
        <Paper
          sx={{
            width: 340,
            maxHeight: 400,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Sticky Header */}
          <Box
            sx={{
              p: 2,
              pb: 1,
              borderBottom: "1px solid",
              borderColor: "divider",
              backgroundColor: "background.paper",
              position: "sticky",
              top: 0,
              zIndex: 1,
            }}
          >
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Typography variant="h6">Notifications</Typography>
              {/* Clear dismissible job notifications */}
              {/* <Tooltip title="Clear completed and failed downloads (active downloads will remain)">
                <Button
                  size="small"
                  variant="outlined"
                  color="secondary"
                  onClick={clearAllJobNotifications}
                  sx={{ fontSize: '0.7rem', py: 0.5, px: 1 }}
                >
                  Clear Jobs
                </Button>
              </Tooltip> */}
            </Box>
          </Box>

          {/* Scrollable Content */}
          <Box
            sx={{
              flex: 1,
              overflow: "auto",
              p: 2,
              pt: 1,
            }}
          >
            <Stack spacing={1}>
              {notifications.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No notifications
                </Typography>
              )}
              {notifications.map((n) => {
                const iconColor = getStatusIconColor(n.jobStatus);
                const isUnseen = !n.seen;

                return (
                  <Paper
                    key={n.id}
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      display: "flex",
                      flexDirection: "column",
                      gap: 1,
                    }}
                  >
                    <Box
                      sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}
                    >
                      {/* Download Icon with status color and flashing animation for unseen */}
                      <Box
                        sx={{
                          color: iconColor,
                          display: "flex",
                          alignItems: "center",
                          mt: 0.25,
                          fontSize: "1.2rem",
                          ...(isUnseen && {
                            animation: "flash-red 0.5s ease-in-out 3",
                            "@keyframes flash-red": {
                              "0%": { color: iconColor },
                              "50%": { color: "#d32f2f" },
                              "100%": { color: iconColor },
                            },
                          }),
                        }}
                      >
                        <DownloadIcon />
                      </Box>

                      <Typography variant="body2" sx={{ flex: 1 }}>
                        {n.message}
                      </Typography>

                      <Box sx={{ display: "flex", gap: 0.5, flexShrink: 0 }}>
                        {n.actionText && n.onAction && (
                          <Button
                            size="small"
                            variant="contained"
                            onClick={n.onAction}
                          >
                            {n.actionText}
                          </Button>
                        )}

                        {n.type === "sticky-dismissible" && (
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleDismissClick(n)}
                          >
                            Dismiss
                          </Button>
                        )}

                        {n.type === "dismissible" && (
                          <IconButton
                            size="small"
                            onClick={() => dismissNotification(n.id)}
                            sx={{ p: 0.5 }}
                          >
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        )}
                      </Box>
                    </Box>

                    {/* Show job details for all bulk download notifications (PENDING, IN_PROGRESS, COMPLETED) */}
                    {n.jobId && (
                      <Box
                        sx={{
                          mt: 1,
                          display: "flex",
                          flexDirection: "column",
                          gap: 0.5,
                        }}
                      >
                        {/* Progress bar for in-progress jobs */}
                        {(n.jobStatus === "INITIATED" ||
                          n.jobStatus === "ASSESSED" ||
                          n.jobStatus === "STAGING" ||
                          n.jobStatus === "PROCESSING") && (
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                            }}
                          >
                            <Box sx={{ flex: 1 }}>
                              <LinearProgress
                                variant={
                                  (n.jobStatus === "STAGING" ||
                                    n.jobStatus === "PROCESSING") &&
                                  n.progress !== undefined
                                    ? "determinate"
                                    : "indeterminate"
                                }
                                value={
                                  (n.jobStatus === "STAGING" ||
                                    n.jobStatus === "PROCESSING") &&
                                  n.progress !== undefined
                                    ? n.progress
                                    : undefined
                                }
                                // sx={{
                                //   height: 6,
                                //   borderRadius: 3,
                                //   backgroundColor: 'grey.200',
                                //   '& .MuiLinearProgress-bar': {
                                //     backgroundColor: iconColor,
                                //     borderRadius: 3,
                                //   },
                                // }}
                              />
                            </Box>
                            {n.progress !== undefined && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {Math.round(n.progress)}%
                              </Typography>
                            )}
                          </Box>
                        )}

                        {/* Job metadata - shown for all job statuses including PENDING and IN_PROGRESS */}
                        <Box
                          sx={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: 1,
                            alignItems: "center",
                          }}
                        >
                          {n.foundAssetsCount !== undefined && (
                            <Tooltip
                              title={
                                n.smallFilesCount !== undefined &&
                                n.largeFilesCount !== undefined
                                  ? `Zipped files: ${n.smallFilesCount}, Large files: ${n.largeFilesCount}`
                                  : undefined
                              }
                            >
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {n.foundAssetsCount} assets
                              </Typography>
                            </Tooltip>
                          )}

                          {n.totalSize !== undefined && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {formatFileSize(n.totalSize)}
                            </Typography>
                          )}

                          {n.createdAt && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Created: {formatDate(n.createdAt)}
                            </Typography>
                          )}

                          {n.updatedAt && n.updatedAt !== n.createdAt && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Last updated: {formatDate(n.updatedAt)}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    )}

                    {/* Show download links for completed jobs */}
                    {n.jobStatus === "COMPLETED" && n.downloadUrls && (
                      <DownloadLinksDisplay
                        downloadUrls={n.downloadUrls}
                        expiresAt={n.expiresAt}
                        description={
                          n.jobStatus === "COMPLETED" ? undefined : n.message
                        }
                      />
                    )}
                  </Paper>
                );
              })}
            </Stack>
          </Box>
        </Paper>
      </Popover>

      {/* Dismiss Confirmation Dialog */}
      <DismissConfirmationDialog
        open={dismissDialog.open}
        onClose={handleCancelDismiss}
        onConfirm={handleConfirmDismiss}
        notificationMessage={dismissDialog.message}
      />
    </>
  );
};
