import { useEffect, useMemo, useRef, useCallback } from "react";
import { useUserBulkDownloadJobs, useUserBatchDeleteJobs } from "@/api/hooks/useAssets";
import { useNotifications, Notification, jobStatusKey } from "@/components/NotificationCenter";

interface DownloadJobData {
  jobId: string;
  status: "INITIATED" | "ASSESSED" | "STAGING" | "PROCESSING" | "COMPLETED" | "FAILED";
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
  expiresAt?: string | number;
  expiresIn?: string;
  error?: string;
  totalSize?: number;
  foundAssetsCount?: number;
  smallFilesCount?: number;
  largeFilesCount?: number;
  missingAssetsCount?: number;
  description?: string;
}

interface DeleteJobData {
  jobId: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
  totalAssets: number;
  processedAssets: number;
  failedAssets: number;
  progress?: number;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  error?: string;
}

type JobData = DownloadJobData | DeleteJobData;

export const useJobNotifications = () => {
  const { notifications, add, dismiss, update } = useNotifications();
  // Read notifications through a ref wherever depending on them would cycle: the
  // sync effect writes notifications via add/update/dismiss, so a dependency on
  // the array itself would re-run it forever.
  const notificationsRef = useRef(notifications);
  notificationsRef.current = notifications;
  const { data: downloadJobsResponse } = useUserBulkDownloadJobs();
  const { data: deleteJobsResponse } = useUserBatchDeleteJobs();
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
      localStorage.setItem("medialake_dismissed_jobs", JSON.stringify([...dismissedJobs]));
    },
    [getDismissedJobs]
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

    dismissibleJobIds.forEach((_jobId) => {
      const jobKeysToRemove = [...seenJobs].filter((key) => key.startsWith(`${_jobId}:`));
      jobKeysToRemove.forEach((key) => seenJobs.delete(key));
    });

    if (dismissibleJobIds.length > 0) {
      localStorage.setItem("medialake_seen_job_notifications", JSON.stringify([...seenJobs]));
    }

    // Only clear synced jobs for dismissed notifications
    // Keep sticky notifications in sync
  }, [notifications, dismiss, markJobAsDismissed]);

  // Combine both job lists with a type marker.
  //
  // Memoised because `allJobs` is a dependency of the sync effect below. Built
  // inline it was a fresh array of fresh objects on every render, so the effect
  // ran on every render of a component mounted at the app root, re-reading,
  // re-parsing and re-writing the notification keys each time.
  const allJobs = useMemo<Array<JobData & { jobType: "download" | "delete" }>>(() => {
    const downloadJobs = downloadJobsResponse?.data?.jobs || [];
    const deleteJobs = deleteJobsResponse?.data?.jobs || [];
    return [
      ...downloadJobs.map((job) => ({ ...job, jobType: "download" as const })),
      ...deleteJobs.map((job) => ({ ...job, jobType: "delete" as const })),
    ];
  }, [downloadJobsResponse, deleteJobsResponse]);

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

  const isJobNotificationSeen = useCallback(
    (jobId: string, status: string): boolean => {
      return getSeenJobNotifications().has(jobStatusKey(jobId, status));
    },
    [getSeenJobNotifications]
  );

  /**
   * Record that a job reached a status the user has not looked at yet.
   *
   * Keyed by `jobId:status` — the same key shape `isJobNotificationSeen` reads —
   * so the write is idempotent: re-creating the notification for a job that is
   * still at the same status produces the same key and the set does not grow.
   *
   * It previously keyed on the notification's `crypto.randomUUID()`, which is
   * minted fresh every time a notification is created. Nothing ever matched those
   * ids again (the set is only ever read for its `.size`, to badge the bell), and
   * the sync re-creates a notification on every load for any job whose
   * notification is missing from state — so each load appended another uuid that
   * nothing could ever remove short of opening the bell. That is how this key
   * reached 1.7 MB and started throwing QuotaExceededError out of an effect at
   * the app root.
   */
  const markAsUnseen = useCallback(
    (jobId: string, status: string) => {
      const unseen = getUnseenNotifications();
      unseen.add(jobStatusKey(jobId, status));
      localStorage.setItem("medialake_unseen_notifications", JSON.stringify([...unseen]));
    },
    [getUnseenNotifications]
  );

  const jobToNotification = useCallback(
    (job: JobData & { jobType: "download" | "delete" }): Omit<Notification, "id" | "seen"> => {
      // Handle batch delete jobs
      if (job.jobType === "delete") {
        const deleteJob = job as DeleteJobData & { jobType: "delete" };
        const baseNotification = {
          jobId: deleteJob.jobId,
          jobType: "delete" as const,
          jobStatus: deleteJob.status as any,
          createdAt: deleteJob.createdAt,
          updatedAt: deleteJob.updatedAt,
          progress: deleteJob.progress,
          foundAssetsCount: deleteJob.totalAssets,
        };

        switch (deleteJob.status) {
          case "PENDING":
            return {
              ...baseNotification,
              message: `Deleting ${deleteJob.totalAssets} assets...`,
              type: "sticky" as const,
            };
          case "PROCESSING":
            return {
              ...baseNotification,
              message: `Deleting assets: ${deleteJob.progress || 0}% complete (${
                deleteJob.processedAssets
              }/${deleteJob.totalAssets})`,
              type: "sticky" as const,
            };
          case "COMPLETED": {
            const successCount = deleteJob.totalAssets - (deleteJob.failedAssets || 0);
            return {
              ...baseNotification,
              message: `Deleted ${successCount} of ${deleteJob.totalAssets} assets successfully`,
              type: "sticky-dismissible" as const,
            };
          }
          case "FAILED":
            return {
              ...baseNotification,
              message: `Batch delete failed: ${deleteJob.error || "Unknown error"}`,
              type: "dismissible" as const,
              autoCloseMs: 10000,
            };
          case "CANCELLED": {
            const processedBeforeCancellation = deleteJob.processedAssets || 0;
            return {
              ...baseNotification,
              message: `Delete cancelled: ${processedBeforeCancellation} of ${deleteJob.totalAssets} assets were processed`,
              type: "sticky-dismissible" as const,
            };
          }
          default:
            return {
              ...baseNotification,
              message: `Delete status: ${deleteJob.status}`,
              type: "dismissible" as const,
            };
        }
      }

      // Handle bulk download jobs
      const downloadJob = job as DownloadJobData;
      const baseNotification = {
        jobId: downloadJob.jobId,
        jobType: "download" as const,
        jobStatus: downloadJob.status as any,
        createdAt: downloadJob.createdAt,
        updatedAt: downloadJob.updatedAt,
        downloadUrls: downloadJob.downloadUrls,
        expiresAt: downloadJob.expiresAt,
        expiresIn: downloadJob.expiresIn,
        progress: downloadJob.progress,
        totalSize: downloadJob.totalSize,
        foundAssetsCount: downloadJob.foundAssetsCount,
        smallFilesCount: downloadJob.smallFilesCount,
        largeFilesCount: downloadJob.largeFilesCount,
      };

      switch (downloadJob.status) {
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

        case "STAGING": {
          const stagingProgress = downloadJob.progress || 0;
          let stagingMessage = "Preparing download archive...";

          if (stagingProgress > 50) {
            const uploadProgress = Math.round(((stagingProgress - 50) / 50) * 100);
            stagingMessage = `Staging archive: ${uploadProgress}% complete`;
          } else if (stagingProgress > 0) {
            const zipProgress = Math.round((stagingProgress / 50) * 100);
            stagingMessage = `Creating archive: ${zipProgress}% complete`;
          }

          return {
            ...baseNotification,
            message: stagingMessage,
            type: "sticky" as const,
          };
        }

        case "PROCESSING": {
          const progress = downloadJob.progress || 0;
          let progressMessage = "";

          if (progress <= 50) {
            const zipProgress = Math.round((progress / 50) * 100);
            progressMessage = `Creating archive: ${zipProgress}% complete`;
          } else {
            const uploadProgress = Math.round(((progress - 50) / 50) * 100);
            progressMessage = `Staging archive: ${uploadProgress}% complete`;
          }

          return {
            ...baseNotification,
            message: progressMessage,
            type: "sticky" as const,
          };
        }

        case "COMPLETED":
          return {
            ...baseNotification,
            message: downloadJob.description || "Your download is ready!",
            type: "sticky-dismissible" as const,
          };

        case "FAILED":
          return {
            ...baseNotification,
            message: `Download failed: ${downloadJob.error || "Unknown error"}`,
            type: "dismissible" as const,
            autoCloseMs: 10000,
          };

        default:
          return {
            ...baseNotification,
            message: `Download status: ${downloadJob.status}`,
            type: "dismissible" as const,
          };
      }
    },
    []
  );

  const createNotificationForJob = useCallback(
    (job: JobData & { jobType: "download" | "delete" }) => {
      const notification = jobToNotification(job);
      const notificationId = add(notification);

      // Only mark as unseen if this job+status combination hasn't been seen before
      if (!isJobNotificationSeen(job.jobId, job.status)) {
        markAsUnseen(job.jobId, job.status);
      }

      return notificationId;
    },
    [add, jobToNotification, markAsUnseen, isJobNotificationSeen]
  );

  const updateNotificationForJob = useCallback(
    (existingNotification: Notification, job: JobData & { jobType: "download" | "delete" }) => {
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
        if (job.status === "COMPLETED" && existingNotification.jobStatus !== "COMPLETED") {
          if (!isJobNotificationSeen(job.jobId, "COMPLETED")) {
            markAsUnseen(job.jobId, "COMPLETED");
          }
        }
      }
    },
    [update, jobToNotification, markAsUnseen, isJobNotificationSeen]
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
    [notifications, dismiss, markJobAsDismissed]
  );

  // Sync backend jobs with notifications.
  useEffect(() => {
    if (allJobs.length === 0) return;

    const currentNotifications = notificationsRef.current;
    const dismissedJobs = getDismissedJobs();

    // First, remove duplicate notifications for the same job
    const jobNotificationMap = new Map<string, Notification[]>();
    currentNotifications.forEach((notification) => {
      if (notification.jobId) {
        if (!jobNotificationMap.has(notification.jobId)) {
          jobNotificationMap.set(notification.jobId, []);
        }
        jobNotificationMap.get(notification.jobId)!.push(notification);
      }
    });

    // Remove duplicate notifications (keep the most recent one)
    jobNotificationMap.forEach((notificationsForJob) => {
      if (notificationsForJob.length > 1) {
        const sortedNotifications = notificationsForJob.sort((a, b) => {
          const aTime = new Date(a.updatedAt || a.createdAt || 0).getTime();
          const bTime = new Date(b.updatedAt || b.createdAt || 0).getTime();
          return bTime - aTime;
        });

        for (let i = 1; i < sortedNotifications.length; i++) {
          dismiss(sortedNotifications[i].id);
        }
      }
    });

    allJobs.forEach((job) => {
      if (dismissedJobs.has(job.jobId)) {
        return;
      }

      const existingNotifications = currentNotifications.filter((n) => n.jobId === job.jobId);

      if (existingNotifications.length === 0) {
        createNotificationForJob(job);
        syncedJobsRef.current.add(job.jobId);
      } else if (existingNotifications.length === 1) {
        updateNotificationForJob(existingNotifications[0], job);
      }
    });

    // Remove notifications for jobs that no longer exist in backend
    const currentJobIds = new Set(allJobs.map((job) => job.jobId));
    currentNotifications.forEach((notification) => {
      if (notification.jobId && !currentJobIds.has(notification.jobId)) {
        dismiss(notification.id);
        const updatedDismissedJobs = getDismissedJobs();
        updatedDismissedJobs.delete(notification.jobId);
        localStorage.setItem("medialake_dismissed_jobs", JSON.stringify([...updatedDismissedJobs]));

        const seenJobs = getSeenJobNotifications();
        const jobKeysToRemove = [...seenJobs].filter((key) =>
          key.startsWith(`${notification.jobId}:`)
        );
        jobKeysToRemove.forEach((key) => seenJobs.delete(key));
        localStorage.setItem("medialake_seen_job_notifications", JSON.stringify([...seenJobs]));
      }
    });
  }, [allJobs, createNotificationForJob, updateNotificationForJob, dismiss, getDismissedJobs]);

  const markAllAsSeen = useCallback(() => {
    localStorage.removeItem("medialake_unseen_notifications");
  }, []);

  const getUnseenCount = useCallback((): number => {
    return getUnseenNotifications().size;
  }, [getUnseenNotifications]);

  return {
    unseenCount: getUnseenCount(),
    markAllAsSeen,
    isJobSyncing: allJobs.length > 0,
    dismissJobNotification,
    clearAllJobNotifications,
  };
};
