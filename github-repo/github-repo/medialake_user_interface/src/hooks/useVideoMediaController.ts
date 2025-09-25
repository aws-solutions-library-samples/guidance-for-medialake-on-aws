import { useState, useCallback, useRef, useEffect } from "react";
import { VideoViewerRef } from "../components/common/VideoViewer";

export interface VideoMediaController {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  seekTo: (time: number) => void;
  onTimeUpdate: (callback: (time: number) => void) => () => void;
  registerVideoViewer: (
    videoViewerRef: React.RefObject<VideoViewerRef>,
  ) => void;
}

export const useVideoMediaController = (): VideoMediaController => {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const videoViewerRef = useRef<React.RefObject<VideoViewerRef> | null>(null);
  const timeUpdateCallbacksRef = useRef<Set<(time: number) => void>>(new Set());

  const registerVideoViewer = useCallback(
    (viewerRef: React.RefObject<VideoViewerRef>) => {
      videoViewerRef.current = viewerRef;
    },
    [],
  );

  const seekTo = useCallback((time: number) => {
    if (videoViewerRef.current?.current) {
      // The VideoViewer component should expose a seek method
      // We'll need to add this to the VideoViewerRef interface
      const viewer = videoViewerRef.current.current;
      if ("seek" in viewer && typeof viewer.seek === "function") {
        (viewer as any).seek(time);
      }
    }
  }, []);

  const onTimeUpdate = useCallback((callback: (time: number) => void) => {
    timeUpdateCallbacksRef.current.add(callback);

    return () => {
      timeUpdateCallbacksRef.current.delete(callback);
    };
  }, []);

  // Handle time updates from the video player
  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
    timeUpdateCallbacksRef.current.forEach((callback) => callback(time));
  }, []);

  return {
    currentTime,
    duration,
    isPlaying,
    seekTo,
    onTimeUpdate,
    registerVideoViewer,
    handleTimeUpdate,
  } as VideoMediaController & { handleTimeUpdate: (time: number) => void };
};
