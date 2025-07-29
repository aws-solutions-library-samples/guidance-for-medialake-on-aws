import { createTheme, Theme } from "@mui/material/styles";
import { colorTokens, componentTokens, typography } from "./tokens";
import { alpha } from "@mui/material/styles";

export const createUnifiedTheme = (mode: "light" | "dark"): Theme => {
  return createTheme({
    palette: {
      mode,
      background: {
        default:
          mode === "light"
            ? colorTokens.background.default.light
            : colorTokens.background.default.dark,
        paper:
          mode === "light"
            ? colorTokens.background.paper.light
            : colorTokens.background.paper.dark,
      },
      text: {
        primary:
          mode === "light"
            ? colorTokens.text.primary.light
            : colorTokens.text.primary.dark,
        secondary:
          mode === "light"
            ? colorTokens.text.secondary.light
            : colorTokens.text.secondary.dark,
      },
      primary: colorTokens.primary,
      secondary: colorTokens.secondary,
      error: colorTokens.error,
      warning: colorTokens.warning,
      success: colorTokens.success,
      info: colorTokens.info,
      action: {
        active:
          mode === "light"
            ? colorTokens.action.active.light
            : colorTokens.action.active.dark,
        hover:
          mode === "light"
            ? colorTokens.action.hover.light
            : colorTokens.action.hover.dark,
      },
    },
    typography: {
      fontFamily: typography.fontFamily,
      allVariants: {
        color:
          mode === "light"
            ? typography.colors.primary.light
            : typography.colors.primary.dark,
      },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarColor:
              mode === "dark" ? "#6b6b6b transparent" : "#959595 transparent",
            "&::-webkit-scrollbar": {
              width: "8px",
              height: "8px",
            },
            "&::-webkit-scrollbar-track": {
              background: "transparent",
            },
            "&::-webkit-scrollbar-thumb": {
              background: mode === "dark" ? "#6b6b6b" : "#959595",
              borderRadius: "4px",
            },
            "&::-webkit-scrollbar-thumb:hover": {
              background: mode === "dark" ? "#7b7b7b" : "#858585",
            },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            fontWeight: 500,
            borderRadius: "4px",
          },
          contained: ({ theme }) => ({
            backgroundColor: theme.palette.primary.main,
            color: theme.palette.primary.contrastText,
            "&:hover": {
              backgroundColor: theme.palette.primary.dark,
              filter: "brightness(110%)",
            },
            "&:active": {
              backgroundColor: theme.palette.primary.dark,
              filter: "brightness(90%)",
            },
            "&.Mui-disabled": {
              backgroundColor: alpha(theme.palette.primary.main, 0.4),
              color: theme.palette.primary.contrastText,
            },
          }),
          outlined: ({ theme }) => ({
            borderColor: theme.palette.primary.main,
            color: theme.palette.primary.main,
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.main, 0.08),
            },
          }),
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: "transparent",
            borderColor: alpha(theme.palette.divider, 0.1),
          }),
          head: ({ theme }) => ({
            backgroundColor:
              mode === "dark"
                ? alpha(colorTokens.background.default.dark, 0.3)
                : alpha(colorTokens.background.default.light, 0.6),
            fontWeight: 600,
          }),
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundColor: "transparent",
            "&:hover": {
              backgroundColor: alpha(theme.palette.primary.main, 0.05),
            },
            "& .MuiTableCell-root": {
              backgroundColor: "transparent",
            },
          }),
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: ({ theme }) => ({
            backgroundImage: "none",
            backgroundColor: theme.palette.background.paper,
          }),
        },
      },
    },
  });
};

// Amplify UI theme override using the same tokens
export const amplifyTheme = {
  name: "mediaLakeTheme",
  tokens: {
    colors: {
      background: {
        primary: colorTokens.background.default.dark,
        secondary: colorTokens.background.paper.dark,
      },
      font: {
        interactive: colorTokens.text.primary.dark,
      },
      border: {
        primary: "rgba(255, 255, 255, 0.3)",
        secondary: "rgba(255, 255, 255, 0.2)",
      },
    },
    components: {
      button: {
        primary: {
          backgroundColor: colorTokens.primary.main,
          _hover: {
            backgroundColor: colorTokens.primary.dark,
          },
          _active: {
            backgroundColor: colorTokens.primary.dark,
          },
          _focus: {
            backgroundColor: colorTokens.primary.dark,
          },
        },
      },
    },
  },
};
