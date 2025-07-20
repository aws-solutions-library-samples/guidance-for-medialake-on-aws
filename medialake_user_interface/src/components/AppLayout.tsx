import React, { useState } from "react";
import { drawerWidth, collapsedDrawerWidth } from "@/constants";
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

  const gradientBackground = `
        radial-gradient(ellipse at top, ${alpha(
          theme.palette.primary.main,
          0.08,
        )} 0%, transparent 50%),
        radial-gradient(ellipse at bottom, ${alpha(
          theme.palette.secondary.main,
          0.05,
        )} 0%, transparent 50%),
        linear-gradient(135deg, ${theme.palette.background.default} 0%, ${alpha(
          theme.palette.primary.main,
          0.02,
        )} 100%)
    `;

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
              [isRTL ? "marginRight" : "marginLeft"]: `${
                isCollapsed ? collapsedDrawerWidth : drawerWidth
              }px`,
              position: "relative",
              minHeight: "100vh",
            }}
          >
            {/* Top Bar with gradient background blend */}
            <Box
              sx={{
                position: "fixed",
                top: 0,
                right: 0,
                left: 0,
                height: "64px",
                [isRTL ? "paddingRight" : "paddingLeft"]: `${
                  isCollapsed ? collapsedDrawerWidth : drawerWidth
                }px`,
                zIndex: 1100,
                background: `
                            radial-gradient(ellipse at top, ${alpha(
                              theme.palette.primary.main,
                              0.08,
                            )} 0%, transparent 50%),
                            linear-gradient(135deg, ${theme.palette.background.default} 0%, ${alpha(
                              theme.palette.primary.main,
                              0.02,
                            )} 100%)
                        `,
                backdropFilter: "blur(10px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: (theme) =>
                  theme.transitions.create(["padding"], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.leavingScreen,
                  }),
              }}
            >
              <Box
                sx={{
                  width: "100%",
                  paddingLeft: 2,
                  paddingRight: 0,
                }}
              >
                <TopBar />
              </Box>
            </Box>

            {/* Main Content Area - inherits gradient background */}
            <Box
              sx={{
                flexGrow: 1,
                p: 4,
                mt: "64px",
                display: "flex",
                flexDirection: "column",
                minWidth: 0,
                overflow: "auto",
                backgroundColor: "transparent", // Let the gradient show through
              }}
            >
              <Outlet />
            </Box>
          </Box>
        </Box>
        {/* Chat Sidebar - Positioned outside the main layout flow */}
        <ChatSidebar />
      </ChatProvider>
    </SidebarContext.Provider>
  );
};

export default AppLayout;
