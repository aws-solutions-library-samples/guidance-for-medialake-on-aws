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

const ImageViewer: React.FC<ImageViewerProps> = ({ imageSrc, maxHeight = '70vh', filename = 'image_download' }) => {
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
            const canvas = canvasRef.current;
            if (!canvas) return 1;

            // Wait for next frame to ensure canvas is properly sized
            return new Promise<number>(resolve => {
                requestAnimationFrame(() => {
                    const canvasWidth = canvas.clientWidth;
                    const maxHeightNumber = typeof maxHeight === 'string' ? parseFloat(maxHeight) : maxHeight;
                    const canvasHeight = typeof maxHeightNumber === 'number' ? maxHeightNumber : canvas.clientHeight;

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
        img.onload = async () => {
            setBackground(img);
            try {
                const initialScale = await calculateInitialScale(img.width, img.height);
                setScaleSize(initialScale);
                setZoom(initialScale);
                setIsImageLoaded(true);
            } catch (error) {
                console.error('Error calculating initial scale:', error);
                setIsImageLoaded(false);
            }
        };
        img.onerror = () => {
            console.error('Error loading image');
            setIsImageLoaded(false);
        };
        img.src = imageSrc;
    }, [imageSrc, calculateInitialScale]);

    // Redraw the canvas whenever dependencies change
    useEffect(() => {
        if (!isImageLoaded || !background || !canvasRef.current) return;

        // Use requestAnimationFrame to ensure canvas is ready
        const animationFrame = requestAnimationFrame(() => {
            draw();
        });

        return () => cancelAnimationFrame(animationFrame);
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

    const handleCanvasDownload = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        // Create a new canvas
        const newCanvas = document.createElement('canvas');
        newCanvas.width = canvas.width;
        newCanvas.height = canvas.height;

        // Get the context of the new canvas
        const context = newCanvas.getContext('2d');
        if (!context) return;

        // Draw the original canvas onto the new canvas
        context.drawImage(canvas, 0, 0);

        try {
            // Convert the new canvas to a data URL
            const dataUrl = newCanvas.toDataURL('image/png');

            // Create a temporary link element
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = `${filename || 'image'}_modified.png`;

            // Append to the body, click, and remove
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error('Error downloading image:', error);
        }
    };

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
    const handleResize = useCallback(async () => {
        if (!background || !canvasRef.current) return;

        try {
            // Recalculate the initial scale based on the new size
            const initialScale = await calculateInitialScale(background.width, background.height);
            setScaleSize(initialScale);
            // Optionally adjust zoom to maintain the same relative scale
            setZoom((prevZoom) => {
                const scaleRatio = initialScale / scaleSize;
                return prevZoom * scaleRatio;
            });
            // Redraw the image with the new dimensions
            requestAnimationFrame(() => {
                draw();
            });
        } catch (error) {
            console.error('Error handling resize:', error);
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
            }}
        >
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
                    gridColumn: '1 / -1',
                    gridRow: '1 / -1',
                }}
            />
            <Box
                sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    flexDirection: 'row',
                    gap: '8px',
                    zIndex: 1,
                }}
            >
                {toolButtons.map((item, i) => (
                    <Tooltip key={`image-tool-${i}`} title={item.tip}>
                        <IconButton
                            color="primary"
                            onClick={item.onClick}
                        >
                            {item.icon}
                        </IconButton>
                    </Tooltip>
                ))}
            </Box>
        </Box>
    );
};

export default ImageViewer;
