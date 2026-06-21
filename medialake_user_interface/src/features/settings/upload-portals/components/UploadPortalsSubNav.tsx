import React from "react";
import { Box, Divider, Tab, Tabs, Typography } from "@mui/material";
import { useNavigate } from "react-router";

/**
 * UploadPortalsSubNav
 *
 * Shared secondary navigation rendered at the top of the three sibling
 * "Upload Portals" admin list pages:
 *
 *   - Portals    → /settings/upload-portals
 *   - Templates  → /settings/upload-portals/templates
 *   - Themes     → /settings/upload-portals/themes
 *
 * "Portals" is the primary destination — the live, end-user-facing artifacts.
 * "Templates" and "Themes" are the reusable building blocks a portal is
 * assembled from (a Template carries structure + appearance; a Theme carries
 * appearance only), so they are grouped behind a quiet "Building blocks" label
 * rather than sitting as equal siblings to Portals. The routing contract
 * (`active` → route) is unchanged; this is a visual reframing only.
 */
export type UploadPortalsTab = "portals" | "templates" | "themes";

const TAB_ROUTES: Record<UploadPortalsTab, string> = {
  portals: "/settings/upload-portals",
  templates: "/settings/upload-portals/templates",
  themes: "/settings/upload-portals/themes",
};

export interface UploadPortalsSubNavProps {
  /** Which sibling list page is currently active. */
  active: UploadPortalsTab;
}

const UploadPortalsSubNav: React.FC<UploadPortalsSubNavProps> = ({ active }) => {
  const navigate = useNavigate();

  const handleChange = (_event: React.SyntheticEvent, value: UploadPortalsTab) => {
    if (value !== active) {
      navigate(TAB_ROUTES[value]);
    }
  };

  // Two tab strips share one handler. Each strip shows a selection indicator
  // only when its own tab is active; the other falls back to `false` so MUI
  // renders no indicator and emits no "value not found" warning.
  const portalsValue: UploadPortalsTab | false = active === "portals" ? "portals" : false;
  const blocksValue: UploadPortalsTab | false = active === "portals" ? false : active;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        mb: 2,
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <Tabs value={portalsValue} onChange={handleChange} aria-label="Upload portals">
        <Tab label="Portals" value="portals" />
      </Tabs>

      <Divider orientation="vertical" flexItem sx={{ my: 1 }} />

      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
        Building blocks
      </Typography>

      <Tabs value={blocksValue} onChange={handleChange} aria-label="Reusable building blocks">
        <Tab label="Templates" value="templates" />
        <Tab label="Themes" value="themes" />
      </Tabs>
    </Box>
  );
};

export default UploadPortalsSubNav;
