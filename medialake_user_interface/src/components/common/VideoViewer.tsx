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
        //ininitalize Player
        let omp = new OmakasePlayer({
            playerHTMLElementId: 'omakase-player',
            mediaChrome: 'enabled',
        });

        //loadVideo
        omp.loadVideo(videoSrc, 60)
            .subscribe({
                next: (video) => {
                    console.log('Video loaded', video);
                    omp.createTimeline({               //Creating timeline only after loading video
                        style: {
                            ...TIMELINE_STYLE_DARK,
                        },
                        zoomWheelEnabled: false
                    }).subscribe((timelineApi) => { // After Timeline, create a lane
                        console.log('create timeline!');
                        let scrubberLane = timelineApi.getScrubberLane();
                        scrubberLane.style = {
                            ...SCRUBBER_LANE_STYLE_DARK
                        };
                    });
                }
            });
        
        omp.video.onVideoLoaded$.pipe(filter(video => !!video)).subscribe({
            next: (video) => {
                console.log("video criado.")
                console.log(video);
            }
            })

        // omp.video.onVideoLoaded$.pipe(filter(video => !!video)).subscribe({
        //     next: (video) => {
        //         createTimelineLanes();
        //     }
        //     })
        
        
        //     let createTimelineLanes = () => {
        //     markerLane1();
        
        //     }
        
        //     let markerLane1 = () => {
        //     let markerLane = new MarkerLane({
        //         style: {
        //         ...TIMELINE_LANE_STYLE_DARK
        //         },
        //     });
        
        //     omp.timeline!.addTimelineLane(markerLane)
        
        //     let periodMarker = new PeriodMarker({
        //         timeObservation: {
        //         start: 0,
        //         end: 0 + 5,
        //         },
        //         editable: true,
        //         style: {
        //         renderType: 'spanning',
        //         symbolSize: 12,
        //         symbolType: 'triangle'
        //         }
        //     })
        
        //     markerLane.addMarker(periodMarker)
        
        //     periodMarker.onChange$.subscribe({
        //         next: (event) => {
        //         console.log('period marker changed', event);
        //         }
        //     })
        //     }

    }, []);


    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: "100%",
                height: "100%",
            }}
        >
            <div
                style={{
                    display: "flex",
                    flexDirection: "column",
                    width: "1000px",
                }}
            >
                <div style={{ margin: "20px 0 0 0" }}>
                    <div id="omakase-player" />
                </div>
                <div style={{ margin: "20px 0 0 0" }}>
                    <div id="omakase-timeline" />
                </div>
            </div>
        </div>
    );
};

export default VideoViewer;