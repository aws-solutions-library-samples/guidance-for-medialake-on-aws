import React from "react";
import {
  Box,
  Typography,
  useTheme,
  useMediaQuery,
  Container,
  Fade,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { useDirection } from "../contexts/DirectionContext";
import { useSidebar } from "../contexts/SidebarContext";
import { drawerWidth, collapsedDrawerWidth } from "../constants";
import { alpha } from "@mui/material/styles";

const Home: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const isSmall = useMediaQuery(theme.breakpoints.down("sm"));
  const { t } = useTranslation();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";
  const { isCollapsed } = useSidebar();

  return (
    <Box
      component="main"
      sx={{
        position: "fixed",
        top: 64,
        ...(isRTL
          ? { left: 0, right: isCollapsed ? collapsedDrawerWidth : drawerWidth }
          : {
              left: isCollapsed ? collapsedDrawerWidth : drawerWidth,
              right: 0,
            }),
        bottom: 0,
        backgroundColor: "transparent",
        overflowY: "auto",
        overflowX: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: theme.transitions.create(["left", "right"], {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.leavingScreen,
        }),
      }}
    >
      <Container
        maxWidth="lg"
        sx={{ textAlign: "center", px: { xs: 3, sm: 4 } }}
      >
        <Fade in={true} timeout={1200}>
          <Box
            sx={{
              maxWidth: { xs: "100%", sm: 800, md: 900, lg: 1000 },
              mx: "auto",
              position: "relative",
            }}
          >
            {/* Floating background elements for visual appeal */}
            <Box
              sx={{
                position: "absolute",
                top: "-20%",
                left: "10%",
                width: "200px",
                height: "200px",
                background: `radial-gradient(circle, ${alpha(
                  theme.palette.primary.main,
                  0.1,
                )} 0%, transparent 70%)`,
                borderRadius: "50%",
                filter: "blur(40px)",
                animation: "float 6s ease-in-out infinite",
                "@keyframes float": {
                  "0%, 100%": { transform: "translateY(0px)" },
                  "50%": { transform: "translateY(-20px)" },
                },
              }}
            />

            <Box
              sx={{
                position: "absolute",
                bottom: "-20%",
                right: "15%",
                width: "150px",
                height: "150px",
                background: `radial-gradient(circle, ${alpha(
                  theme.palette.secondary.main,
                  0.08,
                )} 0%, transparent 70%)`,
                borderRadius: "50%",
                filter: "blur(30px)",
                animation: "float 8s ease-in-out infinite reverse",
              }}
            />

            {/* Main Header */}
            <Typography
              variant={isSmall ? "h2" : isMobile ? "h1" : "h1"}
              component="h1"
              sx={{
                fontWeight: 800,
                background: `linear-gradient(45deg, ${theme.palette.primary.main} 20%, ${theme.palette.secondary.main} 80%)`,
                backgroundClip: "text",
                WebkitBackgroundClip: "text",
                color: "transparent",
                mb: { xs: 2, sm: 2.5, md: 3 },
                letterSpacing: { xs: "-0.02em", sm: "-0.03em", md: "-0.04em" },
                fontSize: {
                  xs: "2.5rem",
                  sm: "3.5rem",
                  md: "4.5rem",
                  lg: "5.5rem",
                  xl: "6rem",
                },
                lineHeight: { xs: 1.1, sm: 1.15, md: 1.2 },
                textShadow: `0 8px 32px ${alpha(theme.palette.primary.main, 0.2)}`,
                position: "relative",
                zIndex: 2,
                "&::after": {
                  content: '""',
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  transform: "translate(-50%, -50%)",
                  width: "120%",
                  height: "120%",
                  background: `radial-gradient(ellipse, ${alpha(
                    theme.palette.primary.main,
                    0.05,
                  )} 0%, transparent 70%)`,
                  borderRadius: "50%",
                  zIndex: -1,
                },
              }}
            >
              {t("app.branding.name")}
            </Typography>

            {/* Visual separator */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: { xs: 2, sm: 2.5, md: 3 },
              }}
            >
              <Box
                sx={{
                  width: { xs: 80, sm: 120, md: 160 },
                  height: 1,
                  background: `linear-gradient(90deg, transparent 0%, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 70%, transparent 100%)`,
                  opacity: 0.4,
                }}
              />
            </Box>

            {/* Subtitle */}
            <Typography
              variant={isSmall ? "h5" : isMobile ? "h4" : "h3"}
              component="p"
              sx={{
                fontWeight: 300,
                color: theme.palette.text.primary,
                lineHeight: { xs: 1.4, sm: 1.5, md: 1.6 },
                fontSize: {
                  xs: "1.25rem",
                  sm: "1.5rem",
                  md: "2rem",
                  lg: "2.25rem",
                },
                maxWidth: { xs: "100%", sm: 600, md: 750, lg: 800 },
                mx: "auto",
                opacity: 0.9,
              }}
            >
              {t("home.description")}
            </Typography>
          </Box>
        </Fade>
      </Container>
    </Box>
  );
};

export default Home;
