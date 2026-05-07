// Re-export from the root constants file.
// TypeScript resolves `@/constants` to `src/constants.ts` (file takes precedence over directory),
// so the canonical definitions live there. This barrel exists for any direct directory imports.
export {
  drawerWidth,
  collapsedDrawerWidth,
  layoutTokens,
  springEasing,
  motion,
} from "../constants";
