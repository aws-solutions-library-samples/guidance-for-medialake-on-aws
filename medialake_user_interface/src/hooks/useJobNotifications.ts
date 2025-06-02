import { useEffect, useRef, useCallback } from 'react';
import { useUserBulkDownloadJobs } from '@/api/hooks/useAssets';
import { useNotifications, Notification } from '@/components/NotificationCenter';

interface JobData {
  jobId: string;
  status: 'INITIATED' | 'ASSESSED' | 'STAGING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress?: number;
  createdAt: string;
  updatedAt: string;
  downloadUrls?: {
    zippedFiles?: string;
    files?: string[];
    singleFiles?: string[];
  } | string[];
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

  // Get user jobs from the response
  const userJobs = userJobsResponse?.data?.jobs || [];

  const getUnseenNotifications = useCallback((): Set<string> => {
    try {
      const unseen = localStorage.getItem('medialake_unseen_notifications');
      return new Set(unseen ? JSON.parse(unseen) : []);
    } catch {
      return new Set();
    }
  }, []);

  const markAsUnseen = useCallback((notificationId: string) => {
    const unseenNotifications = getUnseenNotifications();
    unseenNotifications.add(notificationId);
    localStorage.setItem('medialake_unseen_notifications', JSON.stringify([...unseenNotifications]));
  }, [getUnseenNotifications]);

  const jobToNotification = useCallback((job: JobData): Omit<Notification, 'id' | 'seen'> => {
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
      case 'INITIATED':
        return {
          ...baseNotification,
          message: 'Initiating your bulk download...',
          type: 'sticky' as const,
        };

      case 'ASSESSED':
        return {
          ...baseNotification,
          message: 'Assessing download requirements...',
          type: 'sticky' as const,
        };

      case 'STAGING':
        return {
          ...baseNotification,
          message: 'Preparing download archive...',
          type: 'sticky' as const,
        };

      case 'PROCESSING':
        const progressText = job.progress ? ` (${Math.round(job.progress)}%)` : '';
        return {
          ...baseNotification,
          message: `Creating download archive${progressText}...`,
          type: 'sticky' as const,
        };

      case 'COMPLETED':
        return {
          ...baseNotification,
          message: job.description || 'Your download is ready!',
          type: 'sticky-dismissible' as const,
        };

      case 'FAILED':
        return {
          ...baseNotification,
          message: `Download failed: ${job.error || 'Unknown error'}`,
          type: 'dismissible' as const,
          autoCloseMs: 10000,
        };

      default:
        return {
          ...baseNotification,
          message: `Download status: ${job.status}`,
          type: 'dismissible' as const,
        };
    }
  }, []);

  const createNotificationForJob = useCallback((job: JobData) => {
    const notification = jobToNotification(job);
    const notificationId = add(notification);
    
    // Mark as unseen for badge purposes
    markAsUnseen(notificationId);
    
    return notificationId;
  }, [add, jobToNotification, markAsUnseen]);

  const updateNotificationForJob = useCallback((existingNotification: Notification, job: JobData) => {
    const updatedNotification = jobToNotification(job);
    
    // Only update if there's a meaningful change
    if (
      existingNotification.jobStatus !== job.status ||
      existingNotification.message !== updatedNotification.message ||
      JSON.stringify(existingNotification.downloadUrls) !== JSON.stringify(updatedNotification.downloadUrls)
    ) {
      update(existingNotification.id, updatedNotification);
      
      // Mark as unseen if status changed to completed
      if (job.status === 'COMPLETED' && existingNotification.jobStatus !== 'COMPLETED') {
        markAsUnseen(existingNotification.id);
      }
    }
  }, [update, jobToNotification, markAsUnseen]);

  // Sync backend jobs with notifications
  useEffect(() => {
    if (userJobs.length === 0) return;

    userJobs.forEach((job: JobData) => {
      const existingNotification = notifications.find(n => n.jobId === job.jobId);
      
      if (!existingNotification) {
        // Create new notification for new job
        createNotificationForJob(job);
        syncedJobsRef.current.add(job.jobId);
      } else {
        // Update existing notification if status changed
        updateNotificationForJob(existingNotification, job);
      }
    });

    // Remove notifications for jobs that no longer exist in backend
    const currentJobIds = new Set(userJobs.map(job => job.jobId));
    notifications.forEach(notification => {
      if (notification.jobId && !currentJobIds.has(notification.jobId)) {
        dismiss(notification.id);
      }
    });
  }, [userJobs, notifications, createNotificationForJob, updateNotificationForJob, dismiss]);

  const markAllAsSeen = useCallback(() => {
    localStorage.removeItem('medialake_unseen_notifications');
  }, []);

  const getUnseenCount = useCallback((): number => {
    return getUnseenNotifications().size;
  }, [getUnseenNotifications]);

  return {
    unseenCount: getUnseenCount(),
    markAllAsSeen,
    isJobSyncing: userJobs.length > 0,
  };
};