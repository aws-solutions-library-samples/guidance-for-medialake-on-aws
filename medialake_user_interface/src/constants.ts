export const drawerWidth = 260;
export const collapsedDrawerWidth = 72;

/**
 * Layout spacing tokens — centralized so every page shares the same rhythm.
 */
export const layoutTokens = {
  topBarHeight: 64,
  /** Consistent page-level padding used by the content area and individual pages. */
  pagePadding: { xs: 2, sm: 3, md: 4 },
} as const;

/**
 * Spring-style easing curve for sidebar expand/collapse.
 * Replaces the default MUI `sharp` easing with a more organic feel.
 * cubic-bezier approximation of a damped spring (stiffness ~200, damping ~22).
 */
export const springEasing = "cubic-bezier(0.175, 0.885, 0.32, 1.1)";

/**
 * Shared motion tokens so card hovers, panel transitions, and micro-interactions
 * all use the same duration / easing vocabulary.
 */
export const motion = {
  /** Standard hover lift for interactive cards (collections, assets, connectors). */
  cardHover: {
    transition:
      "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
    transform: "translateY(-4px)",
  },
  /** Smaller hover lift for compact cards (stat cards, API key cards). */
  cardHoverSubtle: {
    transition:
      "transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
    transform: "translateY(-2px)",
  },
} as const;
