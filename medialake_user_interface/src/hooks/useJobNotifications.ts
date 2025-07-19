import { useEffect, useRef, useCallback } from "react";
import { useUserBulkDownloadJobs } from "@/api/hooks/useAssets";
import {
  useNotifications,
  Notification,
} from "@/components/NotificationCenter";

interface JobData {
  jobId: string;
  status:
    | "INITIATED"
    | "ASSESSED"
    | "STAGING"
    | "PROCESSING"
    | "COMPLETED"
    | "FAILED";
  progress?: number;
  createdAt: string;
  updatedAt: string;
  downloadUrls?:
    | {
        zippedFiles?: string;
        files?: string[];
        singleFiles?: string[];
      }
    | string[];
  expiresAt?: string;
  expiresIn?: string;
  error?: string;
  totalSize?: number; // Keep as number to match API response
  foundAssetsCount?: number;
  smallFilesCount?: number;
  largeFilesCount?: number;
  missingAssetsCount?: number;
  description?: string;
}

export const useJobNotifications = () => {
  const { notifications, add, dismiss, update } = useNotifications();
  const { data: userJobsResponse } = useUserBulkDownloadJobs();
  const syncedJobsRef = useRef<Set<string>>(new Set());

  // Get dismissed jobs from localStorage
  const getDismissedJobs = useCallback((): Set<string> => {
    try {
      const dismissed = localStorage.getItem("medialake_dismissed_jobs");
      return new Set(dismissed ? JSON.parse(dismissed) : []);
    } catch {
      return new Set();
    }
  }, []);

  // Add job to dismissed list in localStorage
  const markJobAsDismissed = useCallback(
    (jobId: string) => {
      const dismissedJobs = getDismissedJobs();
      dismissedJobs.add(jobId);
      localStorage.setItem(
        "medialake_dismissed_jobs",
        JSON.stringify([...dismissedJobs]),
      );
    },
    [getDismissedJobs],
  );

  // Clear dismissible job notifications only (respects non-dismissible notifications)
  const clearAllJobNotifications = useCallback(() => {
    // Only dismiss notifications that are dismissible (not 'sticky' type)
    notifications.forEach((notification) => {
      if (notification.jobId && notification.type !== "sticky") {
        markJobAsDismissed(notification.jobId);
        dismiss(notification.id);
      }
    });

    // Clear seen job notifications only for dismissed jobs
    const seenJobs = getSeenJobNotifications();
    const dismissibleJobIds = notifications
      .filter((n) => n.jobId && n.type !== "sticky")
      .map((n) => n.jobId);

    dismissibleJobIds.forEach((jobId) => {
      const jobKeysToRemove = [...seenJobs].filter((key) =>
        key.startsWith(`${jobId}:`),
      );
      jobKeysToRemove.forEach((key) => seenJobs.delete(key));
    });

    if (dismissibleJobIds.length > 0) {
      localStorage.setItem(
        "medialake_seen_job_notifications",
        JSON.stringify([...seenJobs]),
      );
    }

    // Only clear synced jobs for dismissed notifications
    // Keep sticky notifications in sync
  }, [notifications, dismiss, markJobAsDismissed]);

  // Get user jobs from the response
  const userJobs = userJobsResponse?.data?.jobs || [];

  const getUnseenNotifications = useCallback((): Set<string> => {
    try {
      const unseen = localStorage.getItem("medialake_unseen_notifications");
      return new Set(unseen ? JSON.parse(unseen) : []);
    } catch {
      return new Set();
    }
  }, []);

  // Track seen job notifications by job ID and status combination
  const getSeenJobNotifications = useCallback((): Set<string> => {
    try {
      const seen = localStorage.getItem("medialake_seen_job_notifications");
      return new Set(seen ? JSON.parse(seen) : []);
    } catch {
      return new Set();
    }
  }, []);

  const markJobAsSeen = useCallback(
    (jobId: string, status: string) => {
      const seenJobs = getSeenJobNotifications();
      const jobKey = `${jobId}:${status}`;
      seenJobs.add(jobKey);
      localStorage.setItem(
        "medialake_seen_job_notifications",
        JSON.stringify([...seenJobs]),
      );
    },
    [getSeenJobNotifications],
  );

  const isJobNotificationSeen = useCallback(
    (jobId: string, status: string): boolean => {
      const seenJobs = getSeenJobNotifications();
      const jobKey = `${jobId}:${status}`;
      return seenJobs.has(jobKey);
    },
    [getSeenJobNotifications],
  );

  const markAsUnseen = useCallback(
    (notificationId: string) => {
      const unseenNotifications = getUnseenNotifications();
      unseenNotifications.add(notificationId);
      localStorage.setItem(
        "medialake_unseen_notifications",
        JSON.stringify([...unseenNotifications]),
      );
    },
    [getUnseenNotifications],
  );

  const jobToNotification = useCallback(
    (job: JobData): Omit<Notification, "id" | "seen"> => {
      const baseNotification = {
        jobId: job.jobId,
        jobStatus: job.status,
        createdAt: job.createdAt,
        updatedAt: job.updatedAt,
        downloadUrls: job.downloadUrls,
        expiresAt: job.expiresAt,
        expiresIn: job.expiresIn,
        progress: job.progress,
        totalSize: job.totalSize,
        foundAssetsCount: job.foundAssetsCount,
        smallFilesCount: job.smallFilesCount,
        largeFilesCount: job.largeFilesCount,
      };

      switch (job.status) {
        case "INITIATED":
          return {
            ...baseNotification,
            message: "Initiating your bulk download...",
            type: "sticky" as const,
          };

        case "ASSESSED":
          return {
            ...baseNotification,
            message: "Assessing download requirements...",
            type: "sticky" as const,
          };

        case "STAGING":
          const stagingProgress = job.progress || 0;
          let stagingMessage = "Preparing download archive...";

          if (stagingProgress > 50) {
            // If progress > 50%, we're in upload phase
            const uploadProgress = Math.round(
              ((stagingProgress - 50) / 50) * 100,
            );
            stagingMessage = `Staging archive: ${uploadProgress}% complete`;
          } else if (stagingProgress > 0) {
            // If progress > 0 but <= 50%, we might be in zip creation phase
            const zipProgress = Math.round((stagingProgress / 50) * 100);
            stagingMessage = `Creating archive: ${zipProgress}% complete`;
          }

          return {
            ...baseNotification,
            message: stagingMessage,
            type: "sticky" as const,
          };

        case "PROCESSING":
          const progress = job.progress || 0;
          let progressMessage = "";

          if (progress <= 50) {
            // Zip creation phase (0-50%)
            const zipProgress = Math.round((progress / 50) * 100);
            progressMessage = `Creating archive: ${zipProgress}% complete`;
          } else {
            // Multipart upload phase (50-100%)
            const uploadProgress = Math.round(((progress - 50) / 50) * 100);
            progressMessage = `Staging archive: ${uploadProgress}% complete`;
          }

          return {
            ...baseNotification,
            message: progressMessage,
            type: "sticky" as const,
          };

        case "COMPLETED":
          return {
            ...baseNotification,
            message: job.description || "Your download is ready!",
            type: "sticky-dismissible" as const,
          };

        case "FAILED":
          return {
            ...baseNotification,
            message: `Download failed: ${job.error || "Unknown error"}`,
            type: "dismissible" as const,
            autoCloseMs: 10000,
          };

        default:
          return {
            ...baseNotification,
            message: `Download status: ${job.status}`,
            type: "dismissible" as const,
          };
      }
    },
    [],
  );

  const createNotificationForJob = useCallback(
    (job: JobData) => {
      const notification = jobToNotification(job);
      const notificationId = add(notification);

      // Only mark as unseen if this job+status combination hasn't been seen before
      if (!isJobNotificationSeen(job.jobId, job.status)) {
        markAsUnseen(notificationId);
      }

      return notificationId;
    },
    [add, jobToNotification, markAsUnseen, isJobNotificationSeen],
  );

  const updateNotificationForJob = useCallback(
    (existingNotification: Notification, job: JobData) => {
      const updatedNotification = jobToNotification(job);

      // Only update if there's a meaningful change
      if (
        existingNotification.jobStatus !== job.status ||
        existingNotification.message !== updatedNotification.message ||
        JSON.stringify(existingNotification.downloadUrls) !==
          JSON.stringify(updatedNotification.downloadUrls)
      ) {
        update(existingNotification.id, updatedNotification);

        // Mark as unseen if status changed to completed and this completion hasn't been seen before
        if (
          job.status === "COMPLETED" &&
          existingNotification.jobStatus !== "COMPLETED"
        ) {
          if (!isJobNotificationSeen(job.jobId, "COMPLETED")) {
            markAsUnseen(existingNotification.id);
          }
        }
      }
    },
    [update, jobToNotification, markAsUnseen, isJobNotificationSeen],
  );

  // Custom dismiss function that tracks dismissed jobs
  const dismissJobNotification = useCallback(
    (notificationId: string) => {
      const notification = notifications.find((n) => n.id === notificationId);
      if (notification?.jobId) {
        markJobAsDismissed(notification.jobId);
      }
      dismiss(notificationId);
    },
    [notifications, dismiss, markJobAsDismissed],
  );

  // Sync backend jobs with notifications
  useEffect(() => {
    if (userJobs.length === 0) return;

    const dismissedJobs = getDismissedJobs();

    // First, remove duplicate notifications for the same job
    const jobNotificationMap = new Map<string, Notification[]>();
    notifications.forEach((notification) => {
      if (notification.jobId) {
        if (!jobNotificationMap.has(notification.jobId)) {
          jobNotificationMap.set(notification.jobId, []);
        }
        jobNotificationMap.get(notification.jobId)!.push(notification);
      }
    });

    // Remove duplicate notifications (keep the most recent one)
    jobNotificationMap.forEach((notificationsForJob, jobId) => {
      if (notificationsForJob.length > 1) {
        // Sort by updatedAt or createdAt, keep the most recent
        const sortedNotifications = notificationsForJob.sort((a, b) => {
          const aTime = new Date(a.updatedAt || a.createdAt || 0).getTime();
          const bTime = new Date(b.updatedAt || b.createdAt || 0).getTime();
          return bTime - aTime;
        });

        // Remove all but the first (most recent) notification
        for (let i = 1; i < sortedNotifications.length; i++) {
          dismiss(sortedNotifications[i].id);
        }
      }
    });

    userJobs.forEach((job: JobData) => {
      // Skip creating notifications for jobs that have been manually dismissed
      if (dismissedJobs.has(job.jobId)) {
        return;
      }

      const existingNotifications = notifications.filter(
        (n) => n.jobId === job.jobId,
      );

      if (existingNotifications.length === 0) {
        // Create new notification for new job
        createNotificationForJob(job);
        syncedJobsRef.current.add(job.jobId);
      } else if (existingNotifications.length === 1) {
        // Update existing notification if status changed
        updateNotificationForJob(existingNotifications[0], job);
      }
      // If there are multiple notifications, the cleanup above should handle it
    });

    // Remove notifications for jobs that no longer exist in backend
    const currentJobIds = new Set(userJobs.map((job) => job.jobId));
    notifications.forEach((notification) => {
      if (notification.jobId && !currentJobIds.has(notification.jobId)) {
        dismiss(notification.id);
        // Also remove from dismissed jobs since the job no longer exists
        const updatedDismissedJobs = getDismissedJobs();
        updatedDismissedJobs.delete(notification.jobId);
        localStorage.setItem(
          "medialake_dismissed_jobs",
          JSON.stringify([...updatedDismissedJobs]),
        );

        // Clean up seen job notifications for this job
        const seenJobs = getSeenJobNotifications();
        const jobKeysToRemove = [...seenJobs].filter((key) =>
          key.startsWith(`${notification.jobId}:`),
        );
        jobKeysToRemove.forEach((key) => seenJobs.delete(key));
        localStorage.setItem(
          "medialake_seen_job_notifications",
          JSON.stringify([...seenJobs]),
        );
      }
    });
  }, [
    userJobs,
    notifications,
    createNotificationForJob,
    updateNotificationForJob,
    dismiss,
    getDismissedJobs,
  ]);

  const markAllAsSeen = useCallback(() => {
    localStorage.removeItem("medialake_unseen_notifications");
  }, []);

  const getUnseenCount = useCallback((): number => {
    return getUnseenNotifications().size;
  }, [getUnseenNotifications]);

  return {
    unseenCount: getUnseenCount(),
    markAllAsSeen,
    isJobSyncing: userJobs.length > 0,
    dismissJobNotification,
    clearAllJobNotifications,
  };
};
