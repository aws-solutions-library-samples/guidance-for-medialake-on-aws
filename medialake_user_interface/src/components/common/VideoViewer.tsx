import { FC, useEffect, useRef } from 'react';
import { MarkerLane, MomentMarker, OmakasePlayer, PeriodMarker } from '@byomakase/omakase-player';
import { filter } from 'rxjs';
import { SCRUBBER_LANE_STYLE, SCRUBBER_LANE_STYLE_DARK, TIMELINE_LANE_STYLE, TIMELINE_LANE_STYLE_DARK, TIMELINE_STYLE, TIMELINE_STYLE_DARK } from './OmakaseTimeLineConstants';
import { randomHexColor } from './utils';
import './VideoViewer.css';
import { Box, Stack, Paper } from '@mui/material';

interface VideoViewerProps {
  videoSrc: string;
}

export const VideoViewer: FC<VideoViewerProps> = ({ videoSrc }) => {
    //create the OmakasePlayer just after changing 
    useEffect(() => {
        console.log("rendered")
        let omp = new OmakasePlayer({
            playerHTMLElementId: 'omakase-player',
            mediaChrome: 'enabled'
          });
        omp.loadVideo(videoSrc, 25)
        .subscribe({
        next: (video) => {
            console.log('Video loaded', video);
        }
    });
        

    },[]);


    return (
        <div id="omakase-player"></div>
    );
};

export default VideoViewer;