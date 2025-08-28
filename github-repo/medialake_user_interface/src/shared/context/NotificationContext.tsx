import React, { createContext, useContext, useState, ReactNode } from "react";
import { Snackbar, Alert, AlertProps } from "@mui/material";

type NotificationSeverity = "success" | "info" | "warning" | "error";

interface NotificationContextType {
  showNotification: (
    message: string,
    severity?: NotificationSeverity,
    duration?: number,
  ) => void;
  hideNotification: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined,
);

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({
  children,
}) => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<NotificationSeverity>("info");
  const [duration, setDuration] = useState(4000);

  const showNotification = (
    msg: string,
    sev: NotificationSeverity = "info",
    dur: number = 4000,
  ) => {
    setMessage(msg);
    setSeverity(sev);
    setDuration(dur);
    setOpen(true);
  };

  const hideNotification = () => {
    setOpen(false);
  };

  return (
    <NotificationContext.Provider
      value={{ showNotification, hideNotification }}
    >
      {children}
      <Snackbar
        open={open}
        autoHideDuration={duration}
        onClose={hideNotification}
        anchorOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <Alert
          onClose={hideNotification}
          severity={severity}
          sx={{ width: "100%" }}
        >
          {message}
        </Alert>
      </Snackbar>
    </NotificationContext.Provider>
  );
};

export const useNotification = (): NotificationContextType => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error(
      "useNotification must be used within a NotificationProvider",
    );
  }
  return context;
};
