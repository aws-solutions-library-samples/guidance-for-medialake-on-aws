import React, { useEffect } from "react";
import { useJobNotifications } from "@/hooks/useJobNotifications";

/**
 * This component handles the synchronization between backend jobs
 * and the notification system. It should be rendered once at the app level.
 */
export const JobNotificationSync: React.FC = () => {
  // Add basic logging to verify the component is working
  useEffect(() => {
    console.log(
      "JobNotificationSync: Starting bulk download job polling every 15 seconds",
    );
  }, []);

  // This hook will automatically sync jobs with notifications
  useJobNotifications();

  // This component doesn't render anything visible
  return null;
};
