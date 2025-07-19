import React, { useRef, useState, useEffect, useCallback } from "react";
import {
  Box,
  IconButton,
  Tooltip,
  useTheme,
  CircularProgress,
} from "@mui/material";
import Rotate90DegreesCwIcon from "@mui/icons-material/Rotate90DegreesCw";
import HomeIcon from "@mui/icons-material/Home";
import LockIcon from "@mui/icons-material/Lock";
import GetAppIcon from "@mui/icons-material/GetApp";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import _ from "lodash";

interface ImageViewerProps {
  imageSrc: string;
  maxHeight?: string | number;
  filename?: string;
}

const ZOOM_FACTOR = 1.07;

const ImageViewer: React.FC<ImageViewerProps> = ({
  imageSrc,
  maxHeight = "70vh",
  filename = "image_download",
}) => {
  const theme = useTheme();
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [rotate, setRotate] = useState(0);
  const [isCanvasLocked, setIsCanvasLocked] = useState(true);
  const [dragging, setDragging] = useState(false);

  const [isFirstDrawComplete, setIsFirstDrawComplete] = useState(false);
  const [isImageReady, setIsImageReady] = useState(false);
  const [background, setBackground] = useState<HTMLImageElement | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const touch = useRef({ x: 0, y: 0 });
  const isZoomingRef = useRef(false);

  // Use local scaleSize so we always have an up-to-date min/max zoom calculation.
  const [scaleSize, setScaleSize] = useState(1);
  const MIN_ZOOM = scaleSize * 0.5;
  const MAX_ZOOM = scaleSize * 5;

  /** Calculate scale to fit image (considering rotation) in the canvas */
  const calculateFitScale = (
    imgW: number,
    imgH: number,
    rot: number,
  ): number => {
    const canvas = canvasRef.current;
    if (!canvas) return 1;
    const cw = canvas.clientWidth;
    const ch = canvas.clientHeight;
    const isRotated = rot % 180 !== 0;
    const [wFit, hFit] = isRotated ? [imgH, imgW] : [imgW, imgH];
    return Math.min(cw / wFit, ch / hFit, 1);
  };

  /** Fit and center the image */
  const fitAndCenter = useCallback(() => {
    if (!background || !canvasRef.current) return;
    const base = calculateFitScale(background.width, background.height, rotate);
    setScaleSize(base);
    setZoom(base);
    setOffset({ x: 0, y: 0 });
  }, [background, rotate]);

  /** Draw loop */
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !background) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const { width: imgW, height: imgH } = background;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;

    ctx.resetTransform();
    ctx.scale(dpr, dpr);

    // background fill
    const bgColor =
      theme.palette.mode === "dark"
        ? theme.palette.background.paper
        : "#ffffff";
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";

    ctx.save();
    ctx.translate(canvas.clientWidth / 2, canvas.clientHeight / 2);
    ctx.rotate((rotate * Math.PI) / 180);
    ctx.scale(zoom, zoom);
    ctx.translate(-imgW / 2 - offset.x, -imgH / 2 - offset.y);
    ctx.drawImage(background, 0, 0);
    ctx.restore();
  }, [background, zoom, offset, rotate, theme.palette]);

  // --- On image load
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setBackground(img);
      setIsInitialized(true);
      setIsImageReady(true);
    };
    img.src = imageSrc;
  }, [imageSrc]);

  // --- On background or rotate, fit and center (skip if dragging/zooming)
  useEffect(() => {
    if (!background) return;
    if (!dragging && !isZoomingRef.current) {
      fitAndCenter();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [background, rotate]);

  // --- On resize, fit and center (skip if dragging/zooming)
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || !background) return;
    const observer = new ResizeObserver(() => {
      if (!dragging && !isZoomingRef.current) {
        fitAndCenter();
      }
    });
    observer.observe(c);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [background, rotate, dragging, fitAndCenter]);

  // --- Drawing effect
  useEffect(() => {
    if (!isInitialized || !background || !canvasRef.current) return;
    const frame = requestAnimationFrame(() => {
      draw();
      if (!isFirstDrawComplete) setIsFirstDrawComplete(true);
    });
    return () => cancelAnimationFrame(frame);
  }, [isInitialized, background, draw, isFirstDrawComplete]);

  // --- Animation frame request helper
  const animationFrameRef = useRef<number | null>(null);
  const isRenderPendingRef = useRef(false);
  const requestRender = useCallback(() => {
    if (!isRenderPendingRef.current && isInitialized && background) {
      isRenderPendingRef.current = true;
      animationFrameRef.current = requestAnimationFrame(() => {
        draw();
        isRenderPendingRef.current = false;
        animationFrameRef.current = null;
      });
    }
  }, [draw, isInitialized, background]);

  useEffect(() => {
    requestRender();
  }, [zoom, offset, rotate, requestRender]);

  useEffect(() => {
    return () => {
      if (animationFrameRef.current != null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // --- Zoom & pan handlers
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (isCanvasLocked) return;
      e.preventDefault();
      isZoomingRef.current = true;
      const dir = e.deltaY > 0 ? -1 : 1;
      const newZoom = _.clamp(
        zoom * Math.pow(ZOOM_FACTOR, dir),
        MIN_ZOOM,
        MAX_ZOOM,
      );
      setZoom(newZoom);
      setTimeout(() => {
        isZoomingRef.current = false;
      }, 300);
    },
    [isCanvasLocked, zoom, MIN_ZOOM, MAX_ZOOM],
  );

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    if (!isCanvasLocked) {
      c.addEventListener("wheel", handleWheel, { passive: false });
    }
    return () => {
      c.removeEventListener("wheel", handleWheel);
    };
  }, [handleWheel, isCanvasLocked]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isCanvasLocked || !dragging) return;
    const dx = (e.clientX - touch.current.x) / zoom;
    const dy = (e.clientY - touch.current.y) / zoom;
    setOffset((o) => ({ x: o.x - dx, y: o.y - dy }));
    touch.current = { x: e.clientX, y: e.clientY };
  };
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isCanvasLocked) return;
    touch.current = { x: e.clientX, y: e.clientY };
    setDragging(true);
  };
  const handleMouseUp = () => setDragging(false);

  const centerImage = () => {
    fitAndCenter();
  };
  const resetImage = () => {
    fitAndCenter();
    setRotate(0);
  };
  const toggleCanvasLock = () => setIsCanvasLocked((l) => !l);

  const handleCanvasDownload = () => {
    const c = canvasRef.current;
    if (!c) return;
    const off = document.createElement("canvas");
    off.width = c.width;
    off.height = c.height;
    const ctx = off.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(c, 0, 0);
    const dataUrl = off.toDataURL("image/png");
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = `${filename || "image"}_modified.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const toolButtons = [
    {
      tip: "Download Canvas",
      icon: <GetAppIcon />,
      onClick: handleCanvasDownload,
    },
    { tip: "Reset", icon: <HomeIcon />, onClick: resetImage },
    {
      tip: isCanvasLocked ? "Unlock canvas" : "Lock canvas",
      icon: isCanvasLocked ? <LockIcon /> : <LockOpenIcon />,
      onClick: toggleCanvasLock,
    },
    {
      tip: "Rotate",
      icon: <Rotate90DegreesCwIcon />,
      onClick: () => setRotate((r) => (r + 90) % 360),
      style: { transform: "rotate(90deg)" },
    },
  ];

  return (
    <Box
      sx={{
        height: maxHeight,
        maxHeight,
        width: "100%",
        display: "grid",
        gridTemplate: "1fr / 1fr",
        position: "relative",
        overflow: "hidden",
        background: "transparent",
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseOut={handleMouseUp}
        onMouseMove={handleMouseMove}
        style={{
          width: "100%",
          height: "100%",
          cursor: isCanvasLocked ? "default" : dragging ? "grabbing" : "grab",
          opacity: isFirstDrawComplete ? 1 : 0,
          transition: "opacity 0.3s ease-in-out",
        }}
      />
      {!isImageReady && (
        <Box
          sx={{
            gridArea: "1 / 1",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <CircularProgress
            size={48}
            sx={{ mb: 2, color: theme.palette.primary.main }}
          />
        </Box>
      )}
      <Box
        sx={{
          position: "absolute",
          bottom: 8,
          right: 8,
          display: "flex",
          gap: 1,
        }}
      >
        {toolButtons.map((b, i) => (
          <Tooltip key={i} title={b.tip}>
            <IconButton onClick={b.onClick} style={b.style}>
              {b.icon}
            </IconButton>
          </Tooltip>
        ))}
      </Box>
    </Box>
  );
};

export default ImageViewer;
