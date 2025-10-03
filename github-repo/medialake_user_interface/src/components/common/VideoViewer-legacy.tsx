// import { FC, useEffect, useRef,useState, forwardRef, useImperativeHandle } from 'react';
// import { MarkerLane, MomentMarker, OmakasePlayer, PeriodMarker, Timeline } from '@byomakase/omakase-player';
// import { filter } from 'rxjs';
// import { SCRUBBER_LANE_STYLE, SCRUBBER_LANE_STYLE_DARK, TIMELINE_LANE_STYLE, TIMELINE_LANE_STYLE_DARK, TIMELINE_STYLE, TIMELINE_STYLE_DARK } from './OmakaseTimeLineConstants';
// import { randomHexColor } from './utils';
// import { Box, Stack, Paper } from '@mui/material';
// import './OmakasePlayer.css'

// interface VideoViewerProps {
//     videoSrc: string;
// }

// export interface VideoViewerRef {
//     hello: () => void;
// }

// interface VideoViewerProps {
//     videoSrc: string;
// }

// export const VideoViewer = forwardRef<VideoViewerRef, VideoViewerProps>(({ videoSrc }, ref) => {
//     const ompRef = useRef<OmakasePlayer | null>(null);
//     const markerLaneRef = useRef<any>(null);
//     useImperativeHandle(ref, () => ({
//         hello: () => {
//             console.log("Hello from VideoViewer!");
//             // You can access ompRef.current here if needed
//             if (markerLaneRef.current && ompRef.current.video) {
//                 let periodMarker = new PeriodMarker({
//                     timeObservation: {
//                       start: ompRef.current.video.getCurrentTime(),
//                       end: ompRef.current.video.getCurrentTime() + 5,
//                     },
//                     editable: true,
//                     style: {
//                       renderType: 'spanning',
//                       symbolSize: 12,
//                       symbolType: 'triangle',
//                       color: randomHexColor(),
//                     }
//                   })
//                 markerLaneRef.current.addMarker(periodMarker);
//             }
//         }
//     }));

//     useEffect(()=>{
//         ompRef.current = new OmakasePlayer({
//             playerHTMLElementId: 'omakase-player',
//             mediaChrome: 'enabled',

//           });
//           ompRef.current.loadVideo(videoSrc, 60)
//           ompRef.current.createTimeline({
//             style: {
//                 // @ts-ignore
//                 ...TIMELINE_STYLE_DARK
//             },
//             zoomWheelEnabled : true
//         }).subscribe((timelineApi)=>{
//             let scrubberLane = timelineApi.getScrubberLane();
//             scrubberLane.style = {
//               ...SCRUBBER_LANE_STYLE_DARK
//             };
//         });
//         ompRef.current.video.onVideoLoaded$.pipe(filter(video => !!video)).subscribe({
//             next: (video) => {
//                 let markerLane = new MarkerLane({
//                     style: {
//                       ...TIMELINE_LANE_STYLE_DARK
//                     },
//                   });
//                 const mainLane = ompRef.current.timeline!.addTimelineLane(markerLane)
//                 markerLaneRef.current = mainLane
//             }
//           })
//     },[])
//     return (
//         <div
//             style={{
//                 display: "flex",
//                 flexDirection: "column",
//                 alignItems: "center",
//                 width: "100%",
//                 height: "100%",
//             }}
//         >
//             <div
//                 style={{
//                     display: "flex",
//                     flexDirection: "column",
//                     width: "1000px",
//                 }}
//             >
//                 <div style={{ margin: "20px 0 0 0" }}>
//                     <div id="omakase-player" />
//                 </div>
//                 <div style={{ margin: "20px 0 0 0" }}>
//                     <div id="omakase-timeline" />

//                 </div>
//             </div>
//         </div>
//     );
// });

// export default VideoViewer;

// VideoViewer.displayName = 'VideoViewer';
