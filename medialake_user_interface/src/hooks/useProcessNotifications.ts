import { useEffect, useRef } from "react";

interface UseProcessNotificationsProps {
  processId: string | null;
  processType: "bulk-download" | "upload" | "processing" | string;
  status?: {
    status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "FAILED" | string;
    progress?: number;
    error?: string;
    downloadUrl?: string;
    [key: string]: any;
  };
  onCompleted?: (result: any) => void;
  addNotification?: (notification: {
    message: string;
    type?: "sticky" | "sticky-dismissible" | "dismissible";
    actionText?: string;
    onAction?: () => void;
    autoCloseMs?: number;
  }) => string;
  dismissNotification?: (id: string) => void;
}

export const useProcessNotifications = ({
  processId,
  processType,
  status,
  onCompleted,
  addNotification,
  dismissNotification,
}: UseProcessNotificationsProps) => {
  const notificationIdRef = useRef<string | null>(null);
  const previousStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (!status || !addNotification) return;

    const currentStatus = status.status;

    // Only update if status has changed
    if (currentStatus === previousStatusRef.current) return;
    previousStatusRef.current = currentStatus;

    // Dismiss previous notification if it exists
    if (notificationIdRef.current && dismissNotification) {
      dismissNotification(notificationIdRef.current);
      notificationIdRef.current = null;
    }

    // Generate messages based on process type
    const getMessages = () => {
      switch (processType) {
        case "bulk-download":
          return {
            pending: "Preparing your bulk download...",
            inProgress: `Creating download archive${
              status.progress ? ` (${Math.round(status.progress)}%)` : ""
            }...`,
            completed: "Your download is ready!",
            failed: `Download failed: ${status.error || "Unknown error"}`,
            actionText: "Download",
          };
        case "upload":
          return {
            pending: "Preparing upload...",
            inProgress: `Uploading files${
              status.progress ? ` (${Math.round(status.progress)}%)` : ""
            }...`,
            completed: "Upload completed successfully!",
            failed: `Upload failed: ${status.error || "Unknown error"}`,
            actionText: "View",
          };
        case "processing":
          return {
            pending: "Processing started...",
            inProgress: `Processing${
              status.progress ? ` (${Math.round(status.progress)}%)` : ""
            }...`,
            completed: "Processing completed!",
            failed: `Processing failed: ${status.error || "Unknown error"}`,
            actionText: "View Results",
          };
        default:
          return {
            pending: `${processType} started...`,
            inProgress: `${processType} in progress${
              status.progress ? ` (${Math.round(status.progress)}%)` : ""
            }...`,
            completed: `${processType} completed!`,
            failed: `${processType} failed: ${status.error || "Unknown error"}`,
            actionText: "View",
          };
      }
    };

    const messages = getMessages();

    switch (currentStatus) {
      case "PENDING":
        notificationIdRef.current = addNotification({
          message: messages.pending,
          type: "sticky",
        });
        break;

      case "IN_PROGRESS":
        notificationIdRef.current = addNotification({
          message: messages.inProgress,
          type: "sticky",
        });
        break;

      case "COMPLETED":
        notificationIdRef.current = addNotification({
          message: messages.completed,
          type: "sticky-dismissible",
          actionText: messages.actionText,
          onAction: () => {
            if (onCompleted) {
              onCompleted(status);
            } else if (processType === "bulk-download" && status.downloadUrl) {
              // Default download behavior for bulk downloads
              const link = document.createElement("a");
              link.href = status.downloadUrl;
              link.download = `${processType}-${processId}.zip`;
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
            }

            // Dismiss the notification after action
            if (notificationIdRef.current && dismissNotification) {
              dismissNotification(notificationIdRef.current);
              notificationIdRef.current = null;
            }
          },
        });
        break;

      case "FAILED":
        notificationIdRef.current = addNotification({
          message: messages.failed,
          type: "dismissible",
          autoCloseMs: 10000,
        });
        break;
    }
  }, [
    status,
    processId,
    processType,
    addNotification,
    dismissNotification,
    onCompleted,
  ]);

  // Cleanup notification when component unmounts or processId changes
  useEffect(() => {
    return () => {
      if (notificationIdRef.current && dismissNotification) {
        dismissNotification(notificationIdRef.current);
      }
    };
  }, [processId, dismissNotification]);

  return {
    isProcessInProgress:
      !!processId &&
      status?.status !== "COMPLETED" &&
      status?.status !== "FAILED",
  };
};
