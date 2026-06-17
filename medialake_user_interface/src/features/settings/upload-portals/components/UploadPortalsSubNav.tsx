import React from "react";
import { Tabs, Tab } from "@mui/material";
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
 * Templates and Themes were added in task 17.3 as sibling routes (rather
 * than nested tabs inside a single page) so each list keeps its own URL,
 * back-button behavior, and deep-linkable editor routes. This component is
 * the lightweight tab strip that ties the three sibling pages together so
 * an admin can move between them without going back to a parent.
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

  return (
    <Tabs
      value={active}
      onChange={handleChange}
      aria-label="Upload portals sections"
      sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
    >
      <Tab label="Portals" value="portals" />
      <Tab label="Templates" value="templates" />
      <Tab label="Themes" value="themes" />
    </Tabs>
  );
};

export default UploadPortalsSubNav;
