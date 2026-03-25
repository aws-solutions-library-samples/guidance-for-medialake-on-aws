import React, { ReactNode, useState, useEffect, useRef } from "react";
import { Box, Button } from "@mui/material";
import { ChevronLeft, ChevronRight } from "@mui/icons-material";
import { useRightSidebar, COLLAPSED_WIDTH } from "./SidebarContext";
import { alpha } from "@mui/material/styles";
import { springEasing } from "@/constants";
import { zIndexTokens } from "@/theme/tokens";

interface RightSidebarProps {
  children: ReactNode;
  alwaysVisible?: boolean;
}

const MIN_WIDTH = 275;
const MAX_WIDTH = 600;

export const RightSidebar: React.FC<RightSidebarProps> = ({ children, alwaysVisible = false }) => {
  const { isExpanded, setIsExpanded, width, setWidth, hasSelectedItems } = useRightSidebar();
  const [isResizing, setIsResizing] = useState(false);
  const resizeHandleRef = useRef<HTMLDivElement | null>(null);

  // Save width to localStorage when it changes
  useEffect(() => {
    if (width !== COLLAPSED_WIDTH) {
      localStorage.setItem("rightSidebarWidth", width.toString());
    }
  }, [width]);

  // Handle resizing
  useEffect(() => {
    const handleResize = (e: MouseEvent) => {
      if (isResizing && isExpanded) {
        const newWidth = window.innerWidth - e.clientX;
        if (newWidth >= MIN_WIDTH && newWidth <= MAX_WIDTH) {
          setWidth(newWidth);
        }
      }
    };

    const handleResizeEnd = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener("mousemove", handleResize);
      document.addEventListener("mouseup", handleResizeEnd);
    }

    return () => {
      document.removeEventListener("mousemove", handleResize);
      document.removeEventListener("mouseup", handleResizeEnd);
    };
  }, [isResizing, isExpanded]);

  // Handle resize start
  const handleResizeStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
  };

  // Don't render sidebar UI when there are no selected items,
  // but always render children so TabbedSidebar can sync hasSelectedItems
  if (!alwaysVisible && !hasSelectedItems) {
    return <Box sx={{ display: "none" }}>{children}</Box>;
  }

  return (
    <>
      {/* Main sidebar container */}
      <Box
        sx={{
          width: isExpanded ? width : COLLAPSED_WIDTH,
          flexShrink: 0,
          borderLeft: "1px solid",
          borderColor: "divider",
          transition: isResizing
            ? "none"
            : (theme) =>
                `width ${theme.transitions.duration.enteringScreen}ms ${springEasing}, border-radius ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
          bgcolor: "background.paper",
          position: "fixed",
          top: 72,
          right: 0,
          height: "calc(100vh - 88px)",
          display: "flex",
          flexDirection: "column",
          zIndex: zIndexTokens.sidebar,
          borderRadius: "16px 0 0 16px",
          boxShadow: (theme) =>
            isExpanded ? `0 4px 20px ${alpha(theme.palette.common.black, 0.1)}` : "none",
          overflow: "hidden",
        }}
      >
        {/* Resize handle */}
        {isExpanded && (
          <Box
            ref={resizeHandleRef}
            onMouseDown={handleResizeStart}
            sx={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "8px",
              height: "100%",
              cursor: "col-resize",
              zIndex: zIndexTokens.resizeHandle,
              "&:hover": {
                backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.1),
              },
            }}
          />
        )}

        <Box
          sx={{
            position: "absolute",
            top: 0,
            height: "100%",
            overflowX: "hidden",
            width: "100%",
          }}
        >
          <Box
            sx={{
              width: "100%",
              height: "100%",
              overflowY: "auto",
              visibility: isExpanded ? "visible" : "hidden",
            }}
          >
            {children}
          </Box>
        </Box>
      </Box>

      {/* Toggle button - positioned outside the main container to avoid being clipped */}
      <Button
        onClick={() => setIsExpanded(!isExpanded)}
        sx={{
          position: "fixed",
          right: isExpanded ? width - 16 : COLLAPSED_WIDTH - 16,
          top: "calc(50vh - 16px)",
          minWidth: "32px",
          width: "32px",
          height: "32px",
          bgcolor: "background.paper",
          borderRadius: "8px",
          boxShadow: (theme) => `0 2px 4px ${alpha(theme.palette.common.black, 0.1)}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid",
          borderColor: "divider",
          zIndex: zIndexTokens.sidebar + 1,
          padding: 0,
          transition: isResizing
            ? "none"
            : (theme) => `right ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
          "&:hover": {
            bgcolor: "background.paper",
            boxShadow: (theme) => `0 4px 8px ${alpha(theme.palette.common.black, 0.12)}`,
          },
        }}
      >
        {isExpanded ? (
          <ChevronRight sx={{ fontSize: 20 }} />
        ) : (
          <ChevronLeft sx={{ fontSize: 20 }} />
        )}
      </Button>

      {/* Spacer to maintain layout */}
      <Box sx={{ width: isExpanded ? width : COLLAPSED_WIDTH, flexShrink: 0 }} />

      {/* Optional overlay for better UX during resizing */}
      {isResizing && (
        <Box
          sx={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: zIndexTokens.sidebar - 1,
            cursor: "col-resize",
          }}
        />
      )}
    </>
  );
};

export default RightSidebar;
