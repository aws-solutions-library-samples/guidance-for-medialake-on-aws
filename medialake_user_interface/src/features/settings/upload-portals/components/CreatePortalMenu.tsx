import React, { useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemButton,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from "@mui/material";
import { Add as AddIcon, ArrowDropDown as ArrowDropDownIcon } from "@mui/icons-material";
import { useNavigate } from "react-router";

import { useListTemplates } from "@/api/hooks/useTemplates";
import { useListThemes } from "@/api/hooks/useThemes";

/**
 * CreatePortalMenu
 *
 * The "Create Portal" entry point on the Portals list page. It is a split
 * control: the primary button creates a blank portal (the legacy behavior),
 * and the adjacent dropdown offers two seeded-create flows added in task
 * 17.3:
 *
 *   - "Start from template" → pick a Template, then navigate to the create
 *     route with `?template=<id>`. `PortalEditorPage` resolves the full
 *     template via `useGetTemplate` and calls
 *     `store.initializeFromSources({ template })`.
 *   - "Apply theme" → pick a Theme, then navigate to the create route with
 *     `?theme=<id>`. `PortalEditorPage` resolves the theme via `useGetTheme`
 *     and calls `store.initializeFromSources({ theme })`.
 *
 * Both seeds are copy-on-create (snapshot, no live link); the seeding logic
 * lives entirely in the editor store (task 17.2). This component only routes
 * the chosen id through a query param.
 *
 * Extension point for task 17.4: the missing-connector warning on
 * create-from-template is intentionally NOT handled here — it belongs to the
 * editor once the template's destinations have been seeded. See the note in
 * `PortalEditorPage`'s seeding effect.
 */
export interface CreatePortalMenuProps {
  /** Disabled state from the caller's permission check. */
  disabled?: boolean;
  /** Tooltip/title surfaced when disabled. */
  title?: string;
}

type PickerMode = "template" | "theme" | null;

const CreatePortalMenu: React.FC<CreatePortalMenuProps> = ({ disabled = false, title }) => {
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [picker, setPicker] = useState<PickerMode>(null);

  // The lists are only needed once a picker opens, but the hooks must run
  // unconditionally (rules of hooks). They are cheap GET requests that fall
  // back to an empty list without permission, and react-query dedupes/caches.
  const templatesQuery = useListTemplates();
  const themesQuery = useListThemes();

  const templates = templatesQuery.data?.data ?? [];
  const themes = themesQuery.data?.data ?? [];

  const handleBlankCreate = () => navigate("/settings/upload-portals/new");

  const openMenu = (event: React.MouseEvent<HTMLElement>) => setMenuAnchor(event.currentTarget);
  const closeMenu = () => setMenuAnchor(null);

  const openTemplatePicker = () => {
    closeMenu();
    setPicker("template");
  };
  const openThemePicker = () => {
    closeMenu();
    setPicker("theme");
  };
  const closePicker = () => setPicker(null);

  const handleSelectTemplate = (templateId: string) => {
    closePicker();
    navigate(`/settings/upload-portals/new?template=${encodeURIComponent(templateId)}`);
  };

  const handleSelectTheme = (themeId: string) => {
    closePicker();
    navigate(`/settings/upload-portals/new?theme=${encodeURIComponent(themeId)}`);
  };

  return (
    <>
      <Button
        variant="contained"
        startIcon={<AddIcon />}
        endIcon={<ArrowDropDownIcon />}
        onClick={openMenu}
        disabled={disabled}
        title={title}
        aria-haspopup="menu"
      >
        Create Portal
      </Button>

      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
        <MenuItem
          onClick={() => {
            closeMenu();
            handleBlankCreate();
          }}
        >
          Blank portal
        </MenuItem>
        <MenuItem onClick={openTemplatePicker}>Start from template…</MenuItem>
        <MenuItem onClick={openThemePicker}>Apply theme…</MenuItem>
      </Menu>

      {/* Template picker */}
      <Dialog open={picker === "template"} onClose={closePicker} fullWidth maxWidth="xs">
        <DialogTitle>Start from template</DialogTitle>
        <DialogContent dividers>
          {templates.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No templates available. Save a portal as a template from the editor toolbar first.
            </Typography>
          ) : (
            <List disablePadding>
              {templates.map((template) => (
                <ListItemButton
                  key={template.templateId}
                  onClick={() => handleSelectTemplate(template.templateId)}
                >
                  <ListItemText
                    primary={template.name}
                    secondary={template.description || undefined}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closePicker}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Theme picker */}
      <Dialog open={picker === "theme"} onClose={closePicker} fullWidth maxWidth="xs">
        <DialogTitle>Apply theme</DialogTitle>
        <DialogContent dividers>
          {themes.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No themes available. Save a portal&apos;s appearance as a theme from the editor
              toolbar first.
            </Typography>
          ) : (
            <List disablePadding>
              {themes.map((theme) => (
                <ListItemButton
                  key={theme.themeId}
                  onClick={() => handleSelectTheme(theme.themeId)}
                >
                  <ListItemText primary={theme.name} secondary={theme.description || undefined} />
                </ListItemButton>
              ))}
            </List>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closePicker}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default CreatePortalMenu;
