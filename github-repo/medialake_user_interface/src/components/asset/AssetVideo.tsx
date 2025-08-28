import React from "react";
import { Box } from "@mui/material";
import { VideoViewer, VideoViewerRef } from "../common/VideoViewer";

import { forwardRef, useImperativeHandle, useRef, useEffect } from "react";
import { OmakasePlayer } from "@byomakase/omakase-player";

interface AssetVideoProps {
  src: string;
  alt?: string;
  onTimeUpdate?: (time: number) => void;
  onVideoElementReady?: (
    videoViewerRef: React.RefObject<VideoViewerRef>,
  ) => void;
}

export const AssetVideo = forwardRef<VideoViewerRef, AssetVideoProps>(
  ({ src, alt, onTimeUpdate, onVideoElementReady }, ref) => {
    // Register the video element when the component mounts
    useEffect(() => {
      if (
        onVideoElementReady &&
        ref &&
        typeof ref === "object" &&
        ref.current
      ) {
        onVideoElementReady(ref as React.RefObject<VideoViewerRef>);
      }
    }, [onVideoElementReady, ref]);

    return (
      <Box
        width="100%"
        height="100%"
        display="flex"
        justifyContent="center"
        alignItems="center"
        sx={{
          "& > div": {
            width: "100%",
            height: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          },
        }}
      >
        <VideoViewer ref={ref} videoSrc={src} onTimeUpdate={onTimeUpdate} />
      </Box>
    );
  },
);

AssetVideo.displayName = "AssetVideo";
export default AssetVideo;
