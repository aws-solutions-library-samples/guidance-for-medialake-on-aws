import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import Rotate90DegreesCwIcon from '@mui/icons-material/Rotate90DegreesCw';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import HomeIcon from '@mui/icons-material/Home';
import _ from 'lodash';
interface ImageViewerProps {
    imageSrc: string;
    maxHeight?: string | number;
}
const SCROLL_SENSITIVITY = 0.0005;
const MAX_ZOOM = 5;
const MIN_ZOOM = 0.5;
export const ImageViewer: React.FC<ImageViewerProps> = ({ imageSrc, maxHeight = '70vh' }) => {
    const [zoom, setZoom] = useState(1);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [rotate, setRotate] = useState(0);
    const [dragging, setDragging] = useState(false);
    const [isImageLoaded, setIsImageLoaded] = useState(false);
    const [scaleSize, setScaleSize] = useState(1);
    const [background, setBackground] = useState<HTMLImageElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const divRef = useRef<HTMLDivElement>(null); // New ref for the div
    const touch = useRef({ x: 0, y: 0 });
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
    useEffect(() => {
        if (isImageLoaded && background) {
            draw();
        }
    }, [isImageLoaded, background, draw]);
    const handleWheel = useCallback((event: WheelEvent) => {
        event.preventDefault();
        const { deltaY } = event;
        setZoom((prevZoom) => {
            const newZoom = _.clamp(prevZoom - deltaY * SCROLL_SENSITIVITY, MIN_ZOOM, MAX_ZOOM);
            return newZoom;
        });
    }, []);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.addEventListener('wheel', handleWheel, { passive: false });
        return () => canvas.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);
    const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
        if (!dragging) return;
        const { clientX, clientY } = event;
        setOffset((prevOffset) => ({
            x: prevOffset.x + (touch.current.x - clientX) / zoom,
            y: prevOffset.y + (touch.current.y - clientY) / zoom,
        }));
        touch.current = { x: clientX, y: clientY };
    };
    const handleMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
        const { clientX, clientY } = event;
        touch.current = { x: clientX, y: clientY };
        setDragging(true);
    };
    const handleMouseUp = () => {
        setDragging(false);
    };
    const centerImage = () => {
        setZoom(scaleSize);
        setOffset({ x: 0, y: 0 });
    };
    const resetImage = () => {
        centerImage();
        setRotate(0);
    };
    const toolButtons = [
        {
            tip: 'Auto scale',
            icon: <ZoomOutMapIcon />,
            onClick: centerImage,
        },
        {
            tip: 'Reset',
            icon: <HomeIcon />,
            onClick: resetImage,
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
    return (
        <div
            ref={divRef} // Use the new divRef here
            className="full-size flex-center flex-align-center"
            style={{ maxHeight }}
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
                        cursor: dragging ? 'grabbing' : 'grab',
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