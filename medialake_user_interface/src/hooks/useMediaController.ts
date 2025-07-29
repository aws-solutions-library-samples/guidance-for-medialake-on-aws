import { useState, useCallback, useRef, useEffect } from "react";
import { VideoViewerRef } from "../components/common/VideoViewer";

export interface MediaController {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  seekTo: (time: number) => void;
  onTimeUpdate: (callback: (time: number) => void) => () => void;
  registerAudioElement: (audioElement: HTMLAudioElement) => void;
  registerVideoElement: (
    videoViewerRef: React.RefObject<VideoViewerRef>,
  ) => void;
  updateCurrentTime: (time: number) => void;
}

export const useMediaController = (): MediaController => {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const videoElementRef = useRef<React.RefObject<VideoViewerRef> | null>(null);
  const timeUpdateCallbacksRef = useRef<Set<(time: number) => void>>(new Set());

  const registerAudioElement = useCallback((audioElement: HTMLAudioElement) => {
    audioElementRef.current = audioElement;

    const handleTimeUpdate = () => {
      const time = audioElement.currentTime;
      setCurrentTime(time);
      timeUpdateCallbacksRef.current.forEach((callback) => callback(time));
    };

    const handleLoadedMetadata = () => {
      setDuration(audioElement.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);

    audioElement.addEventListener("timeupdate", handleTimeUpdate);
    audioElement.addEventListener("loadedmetadata", handleLoadedMetadata);
    audioElement.addEventListener("play", handlePlay);
    audioElement.addEventListener("pause", handlePause);
    audioElement.addEventListener("ended", handleEnded);

    return () => {
      audioElement.removeEventListener("timeupdate", handleTimeUpdate);
      audioElement.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audioElement.removeEventListener("play", handlePlay);
      audioElement.removeEventListener("pause", handlePause);
      audioElement.removeEventListener("ended", handleEnded);
    };
  }, []);

  const seekTo = useCallback((time: number) => {
    if (audioElementRef.current) {
      audioElementRef.current.currentTime = time;
      setCurrentTime(time);
    } else if (videoElementRef.current?.current) {
      // Use the video viewer's seek method
      videoElementRef.current.current.seek(time);
      setCurrentTime(time);
    }
  }, []);

  const onTimeUpdate = useCallback((callback: (time: number) => void) => {
    timeUpdateCallbacksRef.current.add(callback);

    return () => {
      timeUpdateCallbacksRef.current.delete(callback);
    };
  }, []);

  const registerVideoElement = useCallback(
    (videoViewerRef: React.RefObject<VideoViewerRef>) => {
      videoElementRef.current = videoViewerRef;
    },
    [],
  );

  const updateCurrentTime = useCallback((time: number) => {
    setCurrentTime(time);
    timeUpdateCallbacksRef.current.forEach((callback) => callback(time));
  }, []);

  return {
    currentTime,
    duration,
    isPlaying,
    seekTo,
    onTimeUpdate,
    registerAudioElement,
    registerVideoElement,
    updateCurrentTime,
  };
};
