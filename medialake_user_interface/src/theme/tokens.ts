/**
 * Z-index scale — centralized to prevent magic numbers across the codebase.
 */
export const zIndexTokens = {
  stickyContent: 900,
  stickyHeader: 1000,
  appBar: 1100,
  sidebar: 1200,
  resizeHandle: 1300,
  modal: 1400,
  overlay: 1500,
} as const;

/**
 * Border radius scale — semantic names for consistent rounding.
 */
export const radiusTokens = {
  xs: "4px",
  sm: "6px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "9999px",
} as const;

/**
 * Shadow scale — light/dark aware elevation tokens.
 */
export const shadowTokens = {
  sm: {
    light: "0 1px 3px rgba(0, 0, 0, 0.08)",
    dark: "0 1px 3px rgba(0, 0, 0, 0.4)",
  },
  md: {
    light: "0 4px 12px rgba(0, 0, 0, 0.1)",
    dark: "0 4px 12px rgba(0, 0, 0, 0.5)",
  },
  lg: {
    light: "0 8px 24px rgba(0, 0, 0, 0.12)",
    dark: "0 8px 24px rgba(0, 0, 0, 0.6)",
  },
} as const;

/**
 * Brand colors for third-party services.
 */
export const brandTokens = {
  aws: { orange: "#FF9900" },
} as const;

export const colorTokens = {
  background: {
    default: {
      light: "#F4F6FA", // Cool off-white with personality (was generic #f0f2f5)
      dark: "#161D26", // Deep navy-charcoal
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
  // Secondary — cool slate-violet that harmonizes with the blue primary
  secondary: {
    main: "#6366F1", // Indigo-violet accent
    light: "#818CF8",
    dark: "#4F46E5",
    contrastText: "#FFFFFF",
  },
  accent: {
    // Teal for interactive highlights and badges
    main: "#14B8A6",
    light: "#2DD4BF",
    dark: "#0D9488",
    contrastText: "#FFFFFF",
  },
  error: {
    main: "#E53E3E",
    light: "#FC8181",
    dark: "#C53030",
    contrastText: "#FFFFFF",
  },
  warning: {
    main: "#CA8A04", // Gold-yellow — reads as caution without going orange
    light: "#EAB308",
    dark: "#A16207",
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

export const typography = {
  // Display / heading font — distinctive, geometric, modern
  headingFontFamily: "'Plus Jakarta Sans', -apple-system, system-ui, sans-serif",
  // Body / UI font — highly legible, clean, slightly humanist
  fontFamily: "'Source Sans 3', -apple-system, system-ui, sans-serif",
  // Monospace for code blocks and technical data
  monoFontFamily: "Menlo, Monaco, Consolas, 'Courier New', monospace",
  // Typographic scale
  scale: {
    h1: { fontSize: "2.25rem", lineHeight: 1.2, letterSpacing: "-0.025em", fontWeight: 800 },
    h2: { fontSize: "1.875rem", lineHeight: 1.25, letterSpacing: "-0.02em", fontWeight: 700 },
    h3: { fontSize: "1.5rem", lineHeight: 1.3, letterSpacing: "-0.015em", fontWeight: 700 },
    h4: { fontSize: "1.25rem", lineHeight: 1.35, letterSpacing: "-0.01em", fontWeight: 600 },
    h5: { fontSize: "1.1rem", lineHeight: 1.4, letterSpacing: "-0.005em", fontWeight: 600 },
    h6: { fontSize: "1rem", lineHeight: 1.45, letterSpacing: "0em", fontWeight: 600 },
    subtitle1: {
      fontSize: "0.9375rem",
      lineHeight: 1.5,
      letterSpacing: "0.005em",
      fontWeight: 500,
    },
    subtitle2: { fontSize: "0.875rem", lineHeight: 1.5, letterSpacing: "0.005em", fontWeight: 500 },
    body1: { fontSize: "0.9375rem", lineHeight: 1.6, letterSpacing: "0.01em", fontWeight: 400 },
    body2: { fontSize: "0.8125rem", lineHeight: 1.55, letterSpacing: "0.01em", fontWeight: 400 },
    caption: { fontSize: "0.75rem", lineHeight: 1.5, letterSpacing: "0.02em", fontWeight: 400 },
    overline: { fontSize: "0.6875rem", lineHeight: 1.5, letterSpacing: "0.08em", fontWeight: 600 },
    button: { fontSize: "0.875rem", lineHeight: 1.5, letterSpacing: "0.01em", fontWeight: 600 },
  },
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
