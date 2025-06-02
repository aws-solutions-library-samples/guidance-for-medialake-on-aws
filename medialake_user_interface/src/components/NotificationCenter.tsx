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
} from "@mui/material";
import { Notifications as NotificationsIcon, Close as CloseIcon } from "@mui/icons-material";

/**
 * Supported notification behaviour:
 * - **sticky**               : permanent, no dismiss option.
 * - **sticky-dismissible**   : sticky until the user clicks a `Dismiss` button.
 * - **dismissible**          : shows an "X" button and (optionally) auto–closes after a timeout.
 */
export type NotificationType =
  | "sticky"
  | "sticky-dismissible"
  | "dismissible";

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
}

// ──────────────────────────\
//  Context & provider hook  
// ──────────────────────────/
interface NotificationContextValue {
  notifications: Notification[];
  add: (n: Omit<Notification, "id" | "seen">) => string;
  markAsSeen: (id: string) => void;
  dismiss: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

export const useNotifications = (): NotificationContextValue => {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotifications must be inside <NotificationProvider>");
  return ctx;
};

export const NotificationProvider: React.FC<React.PropsWithChildren> = ({
  children,
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const add = useCallback(
    (n: Omit<Notification, "id" | "seen">) => {
      const id = crypto.randomUUID();
      setNotifications((prev) => [...prev, { id, seen: false, ...n }]);
      return id;
    },
    []
  );

  const markAsSeen = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, seen: true } : n))
    );
  }, []);

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

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
      value={{ notifications, add, markAsSeen, dismiss }}
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
  const unseenCount = notifications.filter((n) => !n.seen).length;
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
    notifications.forEach((n) => {
      if (!n.seen) markAsSeen(n.id);
    });
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <>
      <IconButton
        aria-label="notifications"
        onClick={handleClick}
        sx={{ position: "relative" }}
      >
        <NotificationsIcon />
        {unseenCount > 0 && (
          <Badge
            badgeContent={unseenCount}
            color="error"
            sx={{
              position: "absolute",
              top: 0,
              right: 0,
              "& .MuiBadge-badge": {
                fontSize: "0.75rem",
                height: 16,
                minWidth: 16,
              },
            }}
          />
        )}
      </IconButton>

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
        <Paper sx={{ width: 340, maxHeight: 400, overflow: "auto" }}>
          <Box p={2}>
            <Typography variant="h6" gutterBottom>
              Notifications
            </Typography>
            <Stack spacing={1}>
              {notifications.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No notifications
                </Typography>
              )}
              {notifications.map((n) => (
                <Paper
                  key={n.id}
                  variant="outlined"
                  sx={{ p: 1.5, display: "flex", alignItems: "flex-start", gap: 1 }}
                >
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    {n.message}
                  </Typography>

                  <Box sx={{ display: "flex", gap: 0.5, flexShrink: 0 }}>
                    {n.actionText && (
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
                        onClick={() => dismiss(n.id)}
                      >
                        Dismiss
                      </Button>
                    )}

                    {n.type === "dismissible" && (
                      <IconButton
                        size="small"
                        onClick={() => dismiss(n.id)}
                        sx={{ p: 0.5 }}
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </Paper>
              ))}
            </Stack>
          </Box>
        </Paper>
      </Popover>
    </>
  );
};