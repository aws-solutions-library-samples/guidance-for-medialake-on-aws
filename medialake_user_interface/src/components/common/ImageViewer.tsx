import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import Rotate90DegreesCwIcon from '@mui/icons-material/Rotate90DegreesCw';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
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
const ZOOM_FACTOR = 1.1; // Zoom factor per scroll event
export const ImageViewer: React.FC<ImageViewerProps> = ({ imageSrc, maxHeight = '70vh', filename = 'image_download' }) => {
    const [zoom, setZoom] = useState(1);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [rotate, setRotate] = useState(0);
    const [isCanvasLocked, setIsCanvasLocked] = useState(true);
    const [dragging, setDragging] = useState(false);
    const [isImageLoaded, setIsImageLoaded] = useState(false);
    const [scaleSize, setScaleSize] = useState(1);
    const [background, setBackground] = useState<HTMLImageElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const divRef = useRef<HTMLDivElement>(null);
    const touch = useRef({ x: 0, y: 0 });
    const MIN_ZOOM = scaleSize * 0.5;
    const MAX_ZOOM = scaleSize * 5;
    // Calculate the initial scale to fit the image within the canvas
    const calculateInitialScale = useCallback(
        (imgWidth: number, imgHeight: number) => {
            if (!canvasRef.current) return 1;
            const canvasWidth = canvasRef.current.clientWidth;
            const maxHeightNumber = typeof maxHeight === 'string' ? parseFloat(maxHeight) : maxHeight;
            const canvasHeight = typeof maxHeightNumber === 'number' ? maxHeightNumber : canvasRef.current.clientHeight;
            let scale = 1;
            if (imgWidth > canvasWidth || imgHeight > canvasHeight) {
                const scaleX = canvasWidth / imgWidth;
                const scaleY = canvasHeight / imgHeight;
                scale = Math.min(scaleX, scaleY);
            }
            return scale;
        },
        [maxHeight]
    );
    // Function to draw the image on the canvas
    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas || !background) return;
        const context = canvas.getContext('2d');
        if (!context) return;
        const dpr = window.devicePixelRatio || 1;
        const { width: imgWidth, height: imgHeight } = background;
        canvas.width = canvas.clientWidth * dpr;
        canvas.height = canvas.clientHeight * dpr;
        context.resetTransform();
        context.scale(dpr, dpr);
        context.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
        context.save();
        context.translate(canvas.width / (2 * dpr), canvas.height / (2 * dpr));
        context.rotate((rotate * Math.PI) / 180);
        context.scale(zoom, zoom);
        context.translate(-imgWidth / 2 - offset.x, -imgHeight / 2 - offset.y);
        context.drawImage(background, 0, 0);
        context.restore();
    }, [background, zoom, offset, rotate]);
    // Load the image and set initial state
    useEffect(() => {
        const img = new Image();
        img.onload = () => {
            setBackground(img);
            const initialScale = calculateInitialScale(img.width, img.height);
            setScaleSize(initialScale);
            setZoom(initialScale);
            setIsImageLoaded(true);
        };
        img.onerror = () => {
            console.error('Error loading image');
            setIsImageLoaded(false);
        };
        img.src = imageSrc;
    }, [imageSrc, calculateInitialScale]);
    // Redraw the canvas whenever dependencies change
    useEffect(() => {
        if (isImageLoaded && background) {
            draw();
        }
    }, [isImageLoaded, background, draw]);
    // Handle zooming with the mouse wheel using multiplicative zoom
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
        [MIN_ZOOM, MAX_ZOOM, isCanvasLocked]
    );


    // Add and remove the wheel event listener
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        if (!isCanvasLocked) {
            canvas.addEventListener('wheel', handleWheel, { passive: false });
        }
        return () => canvas.removeEventListener('wheel', handleWheel);
    }, [handleWheel, isCanvasLocked]);
    // Handle panning the image
    const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
        if (isCanvasLocked || !dragging) return;
        const { clientX, clientY } = event;
        const deltaX = (clientX - touch.current.x) / zoom;
        const deltaY = (clientY - touch.current.y) / zoom;
        setOffset((prevOffset) => ({
            x: prevOffset.x - deltaX,
            y: prevOffset.y - deltaY,
        }));
        touch.current = { x: clientX, y: clientY };
    };
    const handleDownload = () => {
        // Create a new Image object
        const img = new Image();
        img.crossOrigin = "anonymous";  // This may help with CORS issues
        img.src = imageSrc;

        img.onload = () => {
            // Create a canvas element
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;

            // Draw the image onto the canvas
            const ctx = canvas.getContext('2d');
            ctx?.drawImage(img, 0, 0);

            // Convert the canvas to a blob
            canvas.toBlob((blob) => {
                if (blob) {
                    // Create a URL for the blob
                    const url = URL.createObjectURL(blob);

                    // Create a link element and trigger the download
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = filename || 'image_download.png';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    // Release the blob URL
                    URL.revokeObjectURL(url);
                }
            }, 'image/png');
        };

        img.onerror = () => {
            console.error('Error loading image for download');
            // You might want to show an error message to the user here
        };
    };



    const handleMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
        if (isCanvasLocked) return;
        const { clientX, clientY } = event;
        touch.current = { x: clientX, y: clientY };
        setDragging(true);
    };
    const handleMouseUp = () => {
        setDragging(false);
    };
    // Center and reset the image
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
    // Resize handler
    const handleResize = useCallback(() => {
        if (background) {
            // Recalculate the initial scale based on the new size
            const initialScale = calculateInitialScale(background.width, background.height);
            setScaleSize(initialScale);
            // Optionally adjust zoom to maintain the same relative scale
            setZoom((prevZoom) => {
                const scaleRatio = initialScale / scaleSize;
                return prevZoom * scaleRatio;
            });
            // Redraw the image with the new dimensions
            draw();
        }
    }, [background, calculateInitialScale, draw, scaleSize]);
    // Observe resize events
    useEffect(() => {
        const observer = new ResizeObserver(() => {
            handleResize();
        });
        if (divRef.current) {
            observer.observe(divRef.current);
        }
        return () => {
            observer.disconnect();
        };
    }, [handleResize]);
    // Define the tool buttons
    const toolButtons = [
        // {
        //     tip: 'Auto scale',
        //     icon: <ZoomOutMapIcon />,
        //     onClick: centerImage,
        // },
        {
            tip: 'Download',
            icon: <GetAppIcon />,
            onClick: handleDownload,
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
            onClick: () => {
                setRotate((prevRotate) => (prevRotate + 90) % 360);
            },
            style: {
                transform: 'rotate(90deg)',
            },

        },

    ];
    // Render the component
    return (
        <div
            ref={divRef}
            className="full-size flex-center flex-align-center"
            style={{ height: maxHeight, maxHeight }}
        >
            <Box position="relative" width="100%" height="100%">
                <canvas
                    ref={canvasRef}
                    onMouseDown={handleMouseDown}
                    onMouseUp={handleMouseUp}
                    onMouseOut={handleMouseUp}
                    onMouseMove={handleMouseMove}
                    style={{
                        width: '100%',
                        height: '100%',
                        cursor: isCanvasLocked ? 'default' : (dragging ? 'grabbing' : 'grab'),
                    }}
                />
                {toolButtons.map((item, i) => (
                    <Tooltip key={`image-tool-${i}`} title={item.tip}>
                        <IconButton
                            sx={{
                                position: 'absolute',
                                top: 8,
                                right: 8 + i * 40,
                                backgroundColor: 'rgba(255, 255, 255, 0.7)',
                                '&:hover': {
                                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                                },
                                ...item.style,
                            }}
                            onClick={item.onClick}
                        >
                            {item.icon}
                        </IconButton>
                    </Tooltip>
                ))}
            </Box>
        </div>
    );
};
export default ImageViewer;