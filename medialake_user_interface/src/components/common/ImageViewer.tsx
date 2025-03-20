import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Box, IconButton, Tooltip, useTheme } from '@mui/material';
import Rotate90DegreesCwIcon from '@mui/icons-material/Rotate90DegreesCw';
import HomeIcon from '@mui/icons-material/Home';
import LockIcon from '@mui/icons-material/Lock';
import GetAppIcon from '@mui/icons-material/GetApp';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import _ from 'lodash';

interface ImageViewerProps {
    imageSrc: string;
    maxHeight?: string | number;
    filename?: string;
}

const ZOOM_FACTOR = 1.1;

const ImageViewer: React.FC<ImageViewerProps> = ({
    imageSrc,
    maxHeight = '70vh',
    filename = 'image_download',
}) => {
    const theme = useTheme();
    const [zoom, setZoom] = useState(1);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [rotate, setRotate] = useState(0);
    const [isCanvasLocked, setIsCanvasLocked] = useState(true);
    const [dragging, setDragging] = useState(false);

    // The "base" scale that makes the image fully fit in the container
    const [scaleSize, setScaleSize] = useState(1);
    // Track whether we've done the first "real" drawing yet
    const [isFirstDrawComplete, setIsFirstDrawComplete] = useState(false);
    // Show a "Loading..." overlay until image is ready + initial draw is done
    const [isImageReady, setIsImageReady] = useState(false);
    // Holds the loaded <img> object
    const [background, setBackground] = useState<HTMLImageElement | null>(null);
    // Whether we have finished measuring + setting up the scale
    const [isInitialized, setIsInitialized] = useState(false);

    /**
     * Refs to the DOM elements
     */
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const divRef = useRef<HTMLDivElement>(null);
    const touch = useRef({ x: 0, y: 0 });

    // We'll clamp zoom between half and 5x the "base" scale
    const MIN_ZOOM = scaleSize * 0.5;
    const MAX_ZOOM = scaleSize * 5;

    /**
     * Helper to calculate scale so the image fits in the container.
     */
    const calculateInitialScale = useCallback(
        (imgWidth: number, imgHeight: number): Promise<number> => {
            const canvas = canvasRef.current;
            if (!canvas) return Promise.resolve(1);

            return new Promise<number>((resolve) => {
                // Use a single requestAnimationFrame to ensure final DOM layout
                requestAnimationFrame(() => {
                    const canvasWidth = canvas.clientWidth;

                    // Parse maxHeight string (e.g. "70vh") or number
                    let maxHeightNumber: number;
                    if (typeof maxHeight === 'string') {
                        if (maxHeight.endsWith('vh')) {
                            const vhValue = parseFloat(maxHeight);
                            maxHeightNumber = window.innerHeight * (vhValue / 100);
                        } else {
                            // e.g. "500px"
                            maxHeightNumber = parseFloat(maxHeight);
                        }
                    } else {
                        // numeric
                        maxHeightNumber = maxHeight;
                    }

                    const canvasHeight = maxHeightNumber;

                    let scale = 1;
                    if (imgWidth > canvasWidth || imgHeight > canvasHeight) {
                        const scaleX = canvasWidth / imgWidth;
                        const scaleY = canvasHeight / imgHeight;
                        scale = Math.min(scaleX, scaleY);
                    }
                    resolve(scale);
                });
            });
        },
        [maxHeight]
    );

    /**
     * Draw the image in the canvas with the current scale/offset/rotation.
     */
    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas || !background) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        const dpr = window.devicePixelRatio || 1;
        const { width: imgWidth, height: imgHeight } = background;

        // Scale the canvas to the device pixel ratio
        canvas.width = canvas.clientWidth * dpr;
        canvas.height = canvas.clientHeight * dpr;

        // Reset transform & adjust for dpr
        context.resetTransform();
        context.scale(dpr, dpr);
        
        // Set background color based on theme - use a color that contrasts with the main background
        const bgColor = theme.palette.mode === 'dark' 
            ? theme.palette.background.paper  // Dark mode - slightly lighter than background
            : '#ffffff';                      // Light mode - pure white for contrast
        
        context.fillStyle = bgColor;
        context.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

        // Set image smoothing properties for clarity
        context.imageSmoothingEnabled = true;
        context.imageSmoothingQuality = 'high';

        context.save();
        // Center on canvas
        context.translate(canvas.clientWidth / 2, canvas.clientHeight / 2);
        // Apply rotation
        context.rotate((rotate * Math.PI) / 180);
        // Apply zoom
        context.scale(zoom, zoom);
        // Apply pan offset (note the negative to center the image)
        context.translate(-imgWidth / 2 - offset.x, -imgHeight / 2 - offset.y);

        context.drawImage(background, 0, 0);
        context.restore();
    }, [background, zoom, offset, rotate, theme.palette.mode, theme.palette.background.paper]);

    /**
     * 1) Load the image from `imageSrc`.
     */
    useEffect(() => {
        const img = new Image();
        setIsImageReady(false);
        setIsInitialized(false);
        setIsFirstDrawComplete(false);

        img.onload = async () => {
            setBackground(img);
            try {
                // Compute best-fit scale
                const initialScale = await calculateInitialScale(img.width, img.height);
                setScaleSize(initialScale);
                setZoom(initialScale);
                setOffset({ x: 0, y: 0 });
                setRotate(0);
                setIsInitialized(true);
                setIsImageReady(true);
            } catch (error) {
                console.error('Error calculating initial scale:', error);
                setIsInitialized(true);
                setIsImageReady(true);
            }
        };
        img.src = imageSrc;
    }, [imageSrc, calculateInitialScale]);

    /**
     * 2) Once `isInitialized` is true, do our first draw at the correct scale,
     *    then set `isFirstDrawComplete`.
     */
    useEffect(() => {
        if (!isInitialized || !background || !canvasRef.current) return;

        const drawImage = () => {
            draw();
            if (!isFirstDrawComplete) {
                setIsFirstDrawComplete(true);
            }
        };
        const animationFrame = requestAnimationFrame(drawImage);

        return () => cancelAnimationFrame(animationFrame);
    }, [isInitialized, background, draw, isFirstDrawComplete]);

    /**
     * Handle zoom (wheel) - only if unlocked
     */
    const handleWheel = useCallback(
        (event: WheelEvent) => {
            if (isCanvasLocked) return;
            event.preventDefault();

            const { deltaY } = event;
            setZoom((prevZoom) => {
                const zoomDirection = deltaY > 0 ? -1 : 1;
                const newZoom = _.clamp(
                    prevZoom * Math.pow(ZOOM_FACTOR, zoomDirection),
                    MIN_ZOOM,
                    MAX_ZOOM
                );
                return newZoom;
            });
        },
        [isCanvasLocked, MIN_ZOOM, MAX_ZOOM]
    );

    // Add or remove the wheel listener
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        if (!isCanvasLocked) {
            canvas.addEventListener('wheel', handleWheel, { passive: false });
        }
        return () => {
            canvas.removeEventListener('wheel', handleWheel);
        };
    }, [handleWheel, isCanvasLocked]);

    /**
     * Handle panning with mouse
     */
    const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
        if (isCanvasLocked || !dragging) return;

        const { clientX, clientY } = event;
        // Panning is inversely affected by zoom
        const deltaX = (clientX - touch.current.x) / zoom;
        const deltaY = (clientY - touch.current.y) / zoom;

        setOffset((prevOffset) => ({
            x: prevOffset.x - deltaX,
            y: prevOffset.y - deltaY,
        }));

        touch.current = { x: clientX, y: clientY };
    };

    const handleMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
        if (isCanvasLocked) return;
        touch.current = { x: event.clientX, y: event.clientY };
        setDragging(true);
    };

    const handleMouseUp = () => {
        setDragging(false);
    };

    /**
     * Reset & Center
     */
    const centerImage = () => {
        setZoom(scaleSize);
        setOffset({ x: 0, y: 0 });
    };

    const resetImage = () => {
        centerImage();
        setRotate(0);
    };

    const toggleCanvasLock = () => {
        setIsCanvasLocked(!isCanvasLocked);
    };

    /**
     * Download
     */
    const handleCanvasDownload = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        // Create a new offscreen canvas to avoid forcing user retina scaling
        const newCanvas = document.createElement('canvas');
        newCanvas.width = canvas.width;
        newCanvas.height = canvas.height;

        const context = newCanvas.getContext('2d');
        if (!context) return;

        // Draw the rendered content
        context.drawImage(canvas, 0, 0);

        try {
            const dataUrl = newCanvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = `${filename || 'image'}_modified.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error('Error downloading image:', error);
        }
    };

    /**
     * Handle container resize via ResizeObserver
     */
    const handleResize = useCallback(async () => {
        if (!background || !canvasRef.current) return;
        try {
            const newScaleSize = await calculateInitialScale(background.width, background.height);
            setScaleSize(newScaleSize);

            // Re-fit the image fully on container resize:
            // setZoom(newScaleSize);
            // setOffset({ x: 0, y: 0 });

            // Redraw after resizing
            requestAnimationFrame(() => {
                draw();
            });
        } catch (err) {
            console.error('Error handling resize:', err);
        }
    }, [background, calculateInitialScale, draw]);

    // Debounce the resize handler so it doesn't fire too often
    const debouncedHandleResize = useCallback(_.debounce(handleResize, 100), [
        handleResize,
    ]);

    useEffect(() => {
        const observer = new ResizeObserver(debouncedHandleResize);
        if (divRef.current) {
            observer.observe(divRef.current);
        }
        return () => {
            observer.disconnect();
        };
    }, [debouncedHandleResize]);

    /**
     * Tool buttons
     */
    const toolButtons = [
        {
            tip: 'Download Canvas',
            icon: <GetAppIcon />,
            onClick: handleCanvasDownload,
        },
        {
            tip: 'Reset',
            icon: <HomeIcon />,
            onClick: resetImage,
        },
        {
            tip: isCanvasLocked ? 'Unlock canvas' : 'Lock canvas',
            icon: isCanvasLocked ? <LockIcon /> : <LockOpenIcon />,
            onClick: toggleCanvasLock,
        },
        {
            tip: 'Rotate',
            icon: <Rotate90DegreesCwIcon />,
            onClick: () => setRotate((prev) => (prev + 90) % 360),
            style: { transform: 'rotate(90deg)' },
        },
    ];

    return (
        <Box
            ref={divRef}
            sx={{
                height: maxHeight,
                maxHeight,
                width: '100%',
                display: 'grid',
                gridTemplateColumns: '1fr',
                gridTemplateRows: '1fr',
                position: 'relative',
                overflow: 'hidden',
                background: 'transparent',
                backgroundColor: 'transparent !important',
            }}
        >
            {/**
       *  Always render the <canvas>, but hide it until first draw is done.
       *  That ensures there's no flicker or giant image shown briefly.
       */}
            <canvas
                ref={canvasRef}
                onMouseDown={handleMouseDown}
                onMouseUp={handleMouseUp}
                onMouseOut={handleMouseUp}
                onMouseMove={handleMouseMove}
                style={{
                    width: '100%',
                    height: '100%',
                    cursor: isCanvasLocked ? 'default' : dragging ? 'grabbing' : 'grab',
                    gridColumn: '1 / -1',
                    gridRow: '1 / -1',
                    opacity: isFirstDrawComplete ? 1 : 0,
                    transition: 'opacity 0.3s ease-in-out',
                    background: 'transparent',
                }}
            />

            {/**
       *  If not ready, show an overlay
       */}
            {!isImageReady && (
                <Box
                    sx={{
                        width: '100%',
                        height: '100%',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gridColumn: '1 / -1',
                        gridRow: '1 / -1',
                    }}
                >
                    Loading...
                </Box>
            )}

            {/**  Toolbar with buttons */}
            <Box
                sx={{
                    position: 'absolute',
                    bottom: 8,
                    right: 8,
                    display: 'flex',
                    flexDirection: 'row',
                    gap: '8px',
                    zIndex: 1000,
                    bgcolor: 'transparent', // Semi-transparent background for better visibility
                    borderRadius: 1,
                    p: 0.5,
                }}
            >
                {toolButtons.map((item, i) => (
                    <Tooltip key={`image-tool-${i}`} title={item.tip}>
                        <IconButton color="primary" onClick={item.onClick} style={item.style}>
                            {item.icon}
                        </IconButton>
                    </Tooltip>
                ))}
            </Box>
        </Box>
    );
};

export default ImageViewer;
