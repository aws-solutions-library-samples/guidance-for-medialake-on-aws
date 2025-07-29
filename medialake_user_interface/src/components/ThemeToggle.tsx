import React from "react";
import {
  Box,
  IconButton,
  ListItem,
  ListItemButton,
  Tooltip,
  Typography,
  useTheme as useMuiTheme,
} from "@mui/material";
import {
  LightMode as LightIcon,
  DarkMode as DarkIcon,
  SettingsBrightness as SystemIcon,
} from "@mui/icons-material";
import { useTheme } from "../hooks/useTheme";
import { useTranslation } from "react-i18next";
import { useDirection } from "../contexts/DirectionContext";

interface ThemeToggleProps {
  isCollapsed?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  isCollapsed = false,
}) => {
  const { t } = useTranslation();
  const muiTheme = useMuiTheme();
  const { theme, mode, setMode } = useTheme();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  if (isCollapsed) {
    return (
      <ListItem disablePadding sx={{ mt: "auto", mb: 2 }}>
        <Tooltip title={t("common.toggleTheme")} placement="right">
          <ListItemButton
            onClick={() => setMode(theme === "light" ? "dark" : "light")}
            sx={{
              minHeight: 48,
              justifyContent: "center",
              px: 2.5,
              borderRadius: "8px",
              mx: 1,
            }}
          >
            {theme === "light" ? (
              <DarkIcon fontSize="small" />
            ) : (
              <LightIcon fontSize="small" />
            )}
          </ListItemButton>
        </Tooltip>
      </ListItem>
    );
  }

  return (
    <ListItem disablePadding sx={{ mt: "auto", mb: 2 }}>
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          px: 2,
        }}
      >
        <Typography
          variant="body2"
          sx={{
            mb: 1,
            color: muiTheme.palette.text.secondary,
            px: 1,
            textAlign: isRTL ? "right" : "left",
            width: "100%",
          }}
        >
          {t("common.theme")}
        </Typography>
        <Box
          sx={{
            display: "flex",
            gap: 1,
            justifyContent: "space-between",
          }}
        >
          <IconButton
            onClick={() => setMode("light")}
            sx={{
              flex: 1,
              borderRadius: 1,
              bgcolor:
                mode === "light"
                  ? `${muiTheme.palette.primary.main}15`
                  : "transparent",
              color:
                mode === "light"
                  ? muiTheme.palette.primary.main
                  : muiTheme.palette.text.secondary,
            }}
          >
            <LightIcon fontSize="small" />
          </IconButton>
          <IconButton
            onClick={() => setMode("dark")}
            sx={{
              flex: 1,
              borderRadius: 1,
              bgcolor:
                mode === "dark"
                  ? `${muiTheme.palette.primary.main}15`
                  : "transparent",
              color:
                mode === "dark"
                  ? muiTheme.palette.primary.main
                  : muiTheme.palette.text.secondary,
            }}
          >
            <DarkIcon fontSize="small" />
          </IconButton>
          <IconButton
            onClick={() => setMode("system")}
            sx={{
              flex: 1,
              borderRadius: 1,
              bgcolor:
                mode === "system"
                  ? `${muiTheme.palette.primary.main}15`
                  : "transparent",
              color:
                mode === "system"
                  ? muiTheme.palette.primary.main
                  : muiTheme.palette.text.secondary,
            }}
          >
            <SystemIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
    </ListItem>
  );
};
