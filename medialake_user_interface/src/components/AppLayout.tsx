import React, { useState, useMemo } from "react";
import { drawerWidth, collapsedDrawerWidth, layoutTokens, springEasing } from "@/constants";
import { Box, useTheme } from "@mui/material";
import { Outlet } from "react-router-dom";
import { SidebarContext } from "../contexts/SidebarContext";
import { useDirection } from "../contexts/DirectionContext";
import { ChatProvider } from "../contexts/ChatContext";
import { alpha } from "@mui/material/styles";
import TopBar from "../TopBar";
import Sidebar from "../Sidebar";
import { ChatSidebar } from "../features/chat";

const AppLayout: React.FC = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const { direction } = useDirection();
  const isRTL = direction === "rtl";
  const theme = useTheme();

  /**
   * Single source of truth for the ambient gradient.
   * Both the root container and the fixed topbar reference this value
   * so the gradient is defined once and never drifts out of sync.
   */
  const gradientBackground = useMemo(
    () => `
      radial-gradient(ellipse at top, ${alpha(
        theme.palette.primary.main,
        0.08
      )} 0%, transparent 50%),
      radial-gradient(ellipse at bottom, ${alpha(
        theme.palette.secondary.main,
        0.05
      )} 0%, transparent 50%),
      linear-gradient(135deg, ${theme.palette.background.default} 0%, ${alpha(
        theme.palette.primary.main,
        0.02
      )} 100%)
    `,
    [theme.palette.primary.main, theme.palette.secondary.main, theme.palette.background.default]
  );

  /** Topbar-specific gradient — same radial at top, but drops the bottom radial so
   *  the bar blends cleanly into the content area beneath it. */
  const topBarGradient = useMemo(
    () => `
      radial-gradient(ellipse at top, ${alpha(
        theme.palette.primary.main,
        0.08
      )} 0%, transparent 50%),
      linear-gradient(135deg, ${theme.palette.background.default} 0%, ${alpha(
        theme.palette.primary.main,
        0.02
      )} 100%)
    `,
    [theme.palette.primary.main, theme.palette.background.default]
  );

  const currentDrawerWidth = isCollapsed ? collapsedDrawerWidth : drawerWidth;

  return (
    <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed }}>
      <ChatProvider>
        <Box
          sx={{
            display: "flex",
            flexDirection: isRTL ? "row-reverse" : "row",
            minHeight: "100vh",
            background: gradientBackground,
          }}
        >
          <Sidebar />
          <Box
            component="main"
            sx={{
              display: "flex",
              flexDirection: "column",
              width: "100%",
              [isRTL ? "marginRight" : "marginLeft"]: `${currentDrawerWidth}px`,
              position: "relative",
              minHeight: "100vh",
              transition: `margin ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
            }}
          >
            {/* Top Bar — fixed, with a subtle bottom border for depth */}
            <Box
              sx={{
                position: "fixed",
                top: 0,
                right: 0,
                left: 0,
                height: `${layoutTokens.topBarHeight}px`,
                [isRTL ? "paddingRight" : "paddingLeft"]: `${currentDrawerWidth}px`,
                zIndex: 1100,
                background: topBarGradient,
                backgroundColor: alpha(theme.palette.background.default, 0.85),
                backdropFilter: "blur(10px)",
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.06)}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: `padding ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
              }}
            >
              <Box
                sx={{
                  width: "100%",
                  px: 2,
                }}
              >
                <TopBar />
              </Box>
            </Box>

            {/* Main Content Area — normal document flow, consistent padding */}
            <Box
              sx={{
                flexGrow: 1,
                px: layoutTokens.pagePadding,
                py: 3,
                mt: `${layoutTokens.topBarHeight}px`,
                display: "flex",
                flexDirection: "column",
                minWidth: 0,
                overflow: "auto",
                backgroundColor: "transparent",
              }}
            >
              <Outlet />
            </Box>
          </Box>
        </Box>
        {/* Chat Sidebar — outside the main layout flow */}
        <ChatSidebar />
      </ChatProvider>
    </SidebarContext.Provider>
  );
};

export default AppLayout;
