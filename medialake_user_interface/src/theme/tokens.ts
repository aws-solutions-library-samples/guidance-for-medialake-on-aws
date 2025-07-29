export const colorTokens = {
  background: {
    default: {
      light: "#f0f2f5",
      dark: "#161D26", // Specified dark mode color
    },
    paper: {
      light: "#ffffff",
      dark: "#1E2732", // Slightly lighter than background
    },
  },
  text: {
    primary: {
      light: "rgba(0, 0, 0, 0.87)",
      dark: "rgba(255, 255, 255, 0.87)",
    },
    secondary: {
      light: "rgba(0, 0, 0, 0.6)",
      dark: "rgba(255, 255, 255, 0.6)",
    },
  },
  action: {
    active: {
      light: "#2B6CB0",
      dark: "#4299E1",
    },
    hover: {
      light: "rgba(43, 108, 176, 0.04)",
      dark: "rgba(66, 153, 225, 0.08)",
    },
  },
  primary: {
    main: "#2B6CB0",
    light: "#4299E1",
    dark: "#2C5282",
    contrastText: "#FFFFFF",
  },
  secondary: {
    main: "#4299E1",
    light: "#63B3ED",
    dark: "#2B6CB0",
    contrastText: "#FFFFFF",
  },
  error: {
    main: "#E53E3E",
    light: "#FC8181",
    dark: "#C53030",
    contrastText: "#FFFFFF",
  },
  warning: {
    main: "#DD6B20",
    light: "#F6AD55",
    dark: "#C05621",
    contrastText: "#FFFFFF",
  },
  success: {
    main: "#38A169",
    light: "#68D391",
    dark: "#2F855A",
    contrastText: "#FFFFFF",
  },
  info: {
    main: "#3182CE",
    light: "#63B3ED",
    dark: "#2C5282",
    contrastText: "#FFFFFF",
  },
};

export const componentTokens = {
  button: {
    contained: {
      primary: {
        background: colorTokens.primary.main,
        color: colorTokens.primary.contrastText,
        hover: {
          background: colorTokens.primary.dark,
          filter: "brightness(110%)",
        },
        active: {
          background: colorTokens.primary.dark,
          filter: "brightness(90%)",
        },
      },
      secondary: {
        background: colorTokens.secondary.main,
        color: colorTokens.secondary.contrastText,
        hover: {
          background: colorTokens.secondary.light,
        },
      },
    },
    outlined: {
      primary: {
        border: `1px solid ${colorTokens.primary.main}`,
        color: colorTokens.primary.main,
        hover: {
          background: "rgba(43, 108, 176, 0.08)",
        },
      },
    },
  },
  table: {
    root: {
      backgroundColor: "transparent",
      borderColor: "rgba(255, 255, 255, 0.1)",
    },
    head: (mode: "light" | "dark") => ({
      backgroundColor:
        mode === "dark" ? "rgba(22, 29, 38, 0.3)" : "rgba(240, 242, 245, 0.6)",
    }),
  },
};

export const typography = {
  fontFamily: "Inter, -apple-system, system-ui, sans-serif",
  colors: {
    primary: {
      light: "rgba(0, 0, 0, 0.87)",
      dark: "#FFFFFF",
    },
    secondary: {
      light: "rgba(0, 0, 0, 0.6)",
      dark: "#A0AEC0",
    },
    disabled: {
      light: "rgba(0, 0, 0, 0.38)",
      dark: "#4A5568",
    },
  },
};
