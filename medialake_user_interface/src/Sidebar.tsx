import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { signOut, fetchUserAttributes } from "aws-amplify/auth";
import { useAuth } from "./common/hooks/auth-context";
import { useDirection } from "./contexts/DirectionContext";
import { Can, usePermission, DisabledWrapper } from "./permissions";
import { useFeatureFlag } from "./contexts/FeatureFlagsContext";
import {
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Box,
  useTheme,
  Collapse,
  Typography,
  IconButton,
  Tooltip,
  Button,
  Menu,
  MenuItem,
  Avatar,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  AccountTree as PipelineIcon,
  Settings as SettingsIcon,
  ExpandLess,
  ExpandMore,
  Storage as StorageIcon,
  PermMedia as MediaAssetsIcon,
  PlaylistPlay as ExecutionsIcon,
  ChevronLeft,
  ChevronRight,
  Group as GroupIcon,
  Home as HomeIcon,
  Extension as IntegrationIcon,
  Terrain as LogoIcon,
  Folder as FolderIcon,
  Security as SecurityIcon,
} from "@mui/icons-material";
import { useLocation, useNavigate } from "react-router-dom";
import { useTheme as useCustomTheme } from "./hooks/useTheme";
import { useSidebar } from "./contexts/SidebarContext";
import { ThemeToggle } from "./components/ThemeToggle";

import { drawerWidth, collapsedDrawerWidth, springEasing } from "@/constants";

function Sidebar() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { theme: customTheme } = useCustomTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const { setIsAuthenticated } = useAuth();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { isCollapsed, setIsCollapsed } = useSidebar();
  const { direction } = useDirection();
  const isRTL = direction === "rtl";
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [userInitial, setUserInitial] = useState("U");
  const [userName, setUserName] = useState("");

  useEffect(() => {
    const loadUserInfo = async () => {
      try {
        const attributes = await fetchUserAttributes();
        if (attributes.given_name && attributes.given_name.trim()) {
          setUserInitial(attributes.given_name.trim()[0].toUpperCase());
          setUserName(attributes.given_name.trim());
        } else if (attributes.email && attributes.email.trim()) {
          setUserInitial(attributes.email.trim()[0].toUpperCase());
          setUserName(attributes.email.trim());
        }
      } catch (error) {
        console.error(
          t("app.errors.loadingUserAttributes", "Error loading user attributes:"),
          error
        );
      }
    };
    loadUserInfo();
  }, []);

  const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    try {
      await signOut();
      setIsAuthenticated(false);
      navigate("/sign-in");
    } catch (error) {
      console.error(t("app.errors.signingOut", "Error signing out:"), error);
    }
    handleClose();
  };

  const isActive = (path: string) => location.pathname === path;
  const isSettingsActive = (path: string) => location.pathname.includes(path);

  const getIconColor = (isItemActive: boolean) => {
    if (isItemActive) {
      return theme.palette.primary.main;
    }
    return theme.palette.text.secondary;
  };

  const { ability } = usePermission();

  // Feature flags
  const advancedPermissionsEnabled = useFeatureFlag("advanced-permissions-enabled", false);

  const canViewPipeline = useMemo(() => {
    try {
      return ability?.can("view", "pipeline") ?? false;
    } catch (error) {
      console.error("Error checking pipeline permission:", error);
      return false;
    }
  }, [ability]);

  // Helper function to safely check permissions
  const safePermissionCheck = useCallback(
    (action: string, resource: string) => {
      try {
        return ability?.can(action as any, resource as any) ?? false;
      } catch (error) {
        console.error(`Error checking ${action} permission on ${resource}:`, error);
        // During errors, default to false but log the error
        return false;
      }
    },
    [ability]
  );

  // Memoize permission checks with error handling
  const canViewSettings = useMemo(() => {
    try {
      // Check if user has the settings-menu:view permission (only admins)
      // This controls visibility of the Settings menu in the sidebar
      return safePermissionCheck("view", "settings-menu") ?? false;
    } catch (error) {
      console.error("Error checking settings permission:", error);
      return false;
    }
  }, [safePermissionCheck]);

  // Build menu items based on permissions
  // Items are always shown but greyed out when user lacks permission,
  // except admin-only items (Settings) which are hidden entirely for non-admins.
  const mainMenuItems = [
    {
      text: t("sidebar.menu.home"),
      icon: <HomeIcon />,
      path: "/",
      disabled: false,
      adminOnly: false,
    },
    {
      text: t("sidebar.menu.assets"),
      icon: <MediaAssetsIcon />,
      path: "/assets",
      disabled: false,
      adminOnly: false,
    },
    {
      text: t("sidebar.menu.collections"),
      icon: <FolderIcon />,
      path: "/collections",
      disabled: false,
      adminOnly: false,
    },
    {
      text: t("sidebar.menu.pipelines"),
      icon: <PipelineIcon />,
      path: "/pipelines",
      disabled: !canViewPipeline,
      adminOnly: false,
    },
    {
      text: t("sidebar.menu.pipelineExecutions"),
      icon: <ExecutionsIcon />,
      path: "/executions",
      disabled: !canViewPipeline,
      adminOnly: false,
    },
    {
      text: t("sidebar.menu.settings"),
      icon: <SettingsIcon />,
      onClick: () => setSettingsOpen(!settingsOpen),
      isExpandable: true,
      isExpanded: settingsOpen,
      disabled: false,
      adminOnly: true, // Hidden entirely for non-admins
      visible: canViewSettings,
      subItems: [
        {
          text: t("sidebar.submenu.connectors"),
          icon: <StorageIcon />,
          path: "/settings/connectors",
          disabled: !(
            safePermissionCheck("view", "connector") ||
            safePermissionCheck("view", "settings.connectors")
          ),
        },
        {
          text: t("sidebar.submenu.usersAndGroups", "Users and Groups"),
          icon: <GroupIcon />,
          path: "/settings/users",
          disabled: !(
            safePermissionCheck("view", "user") ||
            safePermissionCheck("view", "group") ||
            safePermissionCheck("view", "settings.users")
          ),
        },
        {
          text: t("sidebar.submenu.permissions", "Permissions"),
          icon: <SecurityIcon />,
          path: "/settings/permissions",
          disabled: !(
            safePermissionCheck("manage", "permission-set") ||
            safePermissionCheck("view", "settings.permissions")
          ),
        },
        {
          text: t("sidebar.submenu.integrations"),
          icon: <IntegrationIcon />,
          path: "/settings/integrations",
          disabled: !(
            safePermissionCheck("view", "integration") ||
            safePermissionCheck("view", "settings.integrations")
          ),
        },
        {
          text: t("sidebar.submenu.system"),
          icon: <SettingsIcon />,
          path: "/settings/system",
          disabled: !(
            safePermissionCheck("view", "settings") ||
            safePermissionCheck("view", "settings.system")
          ),
        },
      ],
    },
  ].filter((item) => !item.adminOnly || item.visible !== false);

  const handleNavigation = (path: string) => {
    // Don't navigate if:
    // 1. We're already on this exact path, or
    // 2. We're on a sub-route of this path (except for root path '/')
    if (location.pathname === path || (path !== "/" && location.pathname.startsWith(path))) {
      return;
    }

    // Log navigation for debugging
    navigate(path);
  };

  const toggleDrawer = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
        flexShrink: 0,
        position: "fixed",
        zIndex: theme.zIndex.drawer + 1,
        height: "100vh",
        transition: `width ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
        "& .MuiDrawer-paper": {
          width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
          boxSizing: "border-box",
          borderRight: isRTL ? "none" : `1px solid ${alpha(theme.palette.divider, 0.12)}`,
          borderLeft: isRTL ? `1px solid ${alpha(theme.palette.divider, 0.12)}` : "none",
          backgroundColor: theme.palette.background.paper,
          position: "fixed",
          height: "100vh",
          top: 0,
          [isRTL ? "right" : "left"]: 0,
          overflow: "visible",
          transition: `width ${theme.transitions.duration.enteringScreen}ms ${springEasing}`,
        },
      }}
    >
      <Box
        sx={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Logo Section */}
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: isCollapsed ? "center" : "flex-start",
            height: 64,
            px: isCollapsed ? 1 : 2,
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          <LogoIcon
            sx={{
              fontSize: "32px",
              color: theme.palette.primary.main,
              marginRight: isRTL ? 0 : isCollapsed ? 0 : 1,
              marginLeft: isRTL ? (isCollapsed ? 0 : 1) : 0,
            }}
          />
          {!isCollapsed && (
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color: theme.palette.primary.main,
              }}
            >
              {t("app.branding.name", "MediaLake")}
            </Typography>
          )}
        </Box>

        <Button
          onClick={toggleDrawer}
          sx={{
            position: "absolute",
            [isRTL ? "left" : "right"]: -16,
            top: "50%",
            transform: "translateY(-50%)",
            minWidth: "32px",
            width: "32px",
            height: "32px",
            bgcolor: "background.paper",
            borderRadius: "8px",
            boxShadow: (theme) => `0 2px 4px ${alpha(theme.palette.common.black, 0.1)}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "1px solid",
            borderColor: "divider",
            zIndex: 9999,
            padding: 0,
            "&:hover": {
              bgcolor: "background.paper",
              boxShadow: (theme) => `0 4px 8px ${alpha(theme.palette.common.black, 0.12)}`,
            },
          }}
        >
          {isCollapsed ? (
            isRTL ? (
              <ChevronLeft sx={{ fontSize: 20 }} />
            ) : (
              <ChevronRight sx={{ fontSize: 20 }} />
            )
          ) : isRTL ? (
            <ChevronRight sx={{ fontSize: 20 }} />
          ) : (
            <ChevronLeft sx={{ fontSize: 20 }} />
          )}
        </Button>
        <List
          sx={{
            flex: 1,
            overflowY: "auto",
            overflowX: "hidden",
            py: 2,
          }}
        >
          {mainMenuItems.map((item) => {
            // Render a single menu item (used for both collapsed and expanded states)
            const renderMenuItem = (menuItem: typeof item) => {
              const itemContent = (
                <React.Fragment key={menuItem.text}>
                  <ListItem disablePadding>
                    {isCollapsed ? (
                      <Tooltip title={menuItem.text} placement="right">
                        <ListItemButton
                          onClick={
                            menuItem.isExpandable
                              ? menuItem.onClick
                              : () => handleNavigation(menuItem.path || "/")
                          }
                          sx={{
                            minHeight: 48,
                            justifyContent: "center",
                            px: 2.5,
                            backgroundColor:
                              isActive(menuItem.path || "") ||
                              (menuItem.isExpandable && menuItem.isExpanded)
                                ? alpha(theme.palette.primary.main, 0.03)
                                : "transparent",
                            "&:hover": {
                              backgroundColor: alpha(theme.palette.primary.main, 0.08),
                            },
                          }}
                        >
                          <ListItemIcon
                            sx={{
                              minWidth: 0,
                              mr: "auto",
                              justifyContent: "center",
                              color: getIconColor(
                                isActive(menuItem.path || "") ||
                                  (menuItem.isExpandable && menuItem.isExpanded)
                              ),
                            }}
                          >
                            {menuItem.icon}
                          </ListItemIcon>
                        </ListItemButton>
                      </Tooltip>
                    ) : (
                      <ListItemButton
                        onClick={
                          menuItem.isExpandable
                            ? menuItem.onClick
                            : () => handleNavigation(menuItem.path || "/")
                        }
                        sx={{
                          backgroundColor:
                            isActive(menuItem.path || "") ||
                            (menuItem.isExpandable && menuItem.isExpanded)
                              ? alpha(theme.palette.primary.main, 0.03)
                              : "transparent",
                          "&:hover": {
                            backgroundColor: alpha(theme.palette.primary.main, 0.08),
                          },
                          borderRight:
                            isActive(menuItem.path || "") && !isRTL
                              ? `3px solid ${theme.palette.primary.main}`
                              : "none",
                          borderLeft:
                            isActive(menuItem.path || "") && isRTL
                              ? `3px solid ${theme.palette.primary.main}`
                              : "none",
                          mx: 1,
                          borderRadius: "8px",
                          flexDirection: "row",
                          justifyContent: isRTL ? "flex-start" : "flex-start",
                        }}
                      >
                        <ListItemIcon
                          sx={{
                            color: getIconColor(
                              isActive(menuItem.path || "") ||
                                (menuItem.isExpandable && menuItem.isExpanded)
                            ),
                            minWidth: "40px",
                          }}
                        >
                          {menuItem.icon}
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight:
                                  isActive(menuItem.path || "") ||
                                  (menuItem.isExpandable && menuItem.isExpanded)
                                    ? 600
                                    : 400,
                                color:
                                  isActive(menuItem.path || "") ||
                                  (menuItem.isExpandable && menuItem.isExpanded)
                                    ? theme.palette.primary.main
                                    : theme.palette.text.primary,
                                textAlign: isRTL ? "right" : "left",
                              }}
                            >
                              {menuItem.text}
                            </Typography>
                          }
                          sx={{ textAlign: isRTL ? "right" : "left" }}
                        />
                        {menuItem.isExpandable && (
                          <Box
                            sx={{
                              color: "text.primary",
                            }}
                          >
                            {menuItem.isExpanded ? <ExpandLess /> : <ExpandMore />}
                          </Box>
                        )}
                      </ListItemButton>
                    )}
                  </ListItem>
                  {!isCollapsed && menuItem.isExpandable && menuItem.subItems && (
                    <Collapse in={menuItem.isExpanded} timeout="auto" unmountOnExit>
                      <List component="div" disablePadding>
                        {menuItem.subItems.map((subItem) => {
                          const subItemContent = (
                            <ListItem key={subItem.text} disablePadding>
                              <ListItemButton
                                onClick={() => handleNavigation(subItem.path)}
                                sx={{
                                  [isRTL ? "pr" : "pl"]: 6,
                                  backgroundColor: isSettingsActive(subItem.path)
                                    ? alpha(theme.palette.primary.main, 0.03)
                                    : "transparent",
                                  "&:hover": {
                                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                                  },
                                  borderRight:
                                    isSettingsActive(subItem.path) && !isRTL
                                      ? `3px solid ${theme.palette.primary.main}`
                                      : "none",
                                  borderLeft:
                                    isSettingsActive(subItem.path) && isRTL
                                      ? `3px solid ${theme.palette.primary.main}`
                                      : "none",
                                  mx: 1,
                                  borderRadius: "8px",
                                  flexDirection: "row",
                                  justifyContent: isRTL ? "flex-start" : "flex-start",
                                }}
                              >
                                <ListItemIcon
                                  sx={{
                                    color: getIconColor(isSettingsActive(subItem.path)),
                                    minWidth: "40px",
                                  }}
                                >
                                  {subItem.icon}
                                </ListItemIcon>
                                <ListItemText
                                  primary={
                                    <Typography
                                      variant="body2"
                                      sx={{
                                        fontWeight: isSettingsActive(subItem.path) ? 600 : 400,
                                        color: isSettingsActive(subItem.path)
                                          ? theme.palette.primary.main
                                          : theme.palette.text.primary,
                                        textAlign: isRTL ? "right" : "left",
                                      }}
                                    >
                                      {subItem.text}
                                    </Typography>
                                  }
                                  sx={{ textAlign: isRTL ? "right" : "left" }}
                                />
                              </ListItemButton>
                            </ListItem>
                          );

                          // Grey out disabled sub-items with tooltip
                          return subItem.disabled ? (
                            <DisabledWrapper
                              key={subItem.text}
                              disabled
                              tooltip={t(
                                "permissions.noPermission",
                                "You don't have permission to access this section"
                              )}
                            >
                              {subItemContent}
                            </DisabledWrapper>
                          ) : (
                            <React.Fragment key={subItem.text}>{subItemContent}</React.Fragment>
                          );
                        })}
                      </List>
                    </Collapse>
                  )}
                </React.Fragment>
              );

              return itemContent;
            };

            // Wrap disabled non-admin items with DisabledWrapper (greyed out + tooltip)
            if (item.disabled) {
              return (
                <DisabledWrapper
                  key={item.text}
                  disabled
                  tooltip={t(
                    "permissions.noPermission",
                    "You don't have permission to access this section"
                  )}
                >
                  {renderMenuItem(item)}
                </DisabledWrapper>
              );
            }

            return <React.Fragment key={item.text}>{renderMenuItem(item)}</React.Fragment>;
          })}
        </List>

        {/* Bottom Section */}
        <Box
          sx={{
            mt: "auto",
            borderTop: "1px solid",
            borderColor: "divider",
            backgroundColor: theme.palette.background.paper,
          }}
        >
          {/* Profile Section */}
          <Box
            sx={{
              px: isCollapsed ? 1 : 2,
              pt: 2,
              pb: 1,
            }}
          >
            {isCollapsed ? (
              <Tooltip title={userName || t("common.profile")} placement="right">
                <IconButton
                  onClick={handleProfileClick}
                  sx={{
                    width: "100%",
                    height: 40,
                    borderRadius: "8px",
                    "&:hover": {
                      backgroundColor: alpha(theme.palette.primary.main, 0.08),
                    },
                  }}
                >
                  <Avatar
                    sx={{
                      width: 32,
                      height: 32,
                      backgroundColor: theme.palette.primary.main,
                      fontSize: "0.9rem",
                    }}
                  >
                    {userInitial}
                  </Avatar>
                </IconButton>
              </Tooltip>
            ) : (
              <Button
                onClick={handleProfileClick}
                sx={{
                  width: "100%",
                  height: 40,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "flex-start",
                  gap: 1.5,
                  borderRadius: "8px",
                  px: 1.5,
                  "&:hover": {
                    backgroundColor: alpha(theme.palette.primary.main, 0.08),
                  },
                }}
              >
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    backgroundColor: theme.palette.primary.main,
                    fontSize: "0.9rem",
                  }}
                >
                  {userInitial}
                </Avatar>
                <Typography
                  variant="body2"
                  sx={{
                    color: theme.palette.text.primary,
                    fontWeight: 500,
                  }}
                >
                  {userName}
                </Typography>
              </Button>
            )}

            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleClose}
              anchorOrigin={{
                vertical: "top",
                horizontal: "right",
              }}
              transformOrigin={{
                vertical: "bottom",
                horizontal: "left",
              }}
              slotProps={{
                paper: {
                  sx: {
                    width: "200px",
                    mt: -1,
                    boxShadow: (theme) => `0 4px 12px ${alpha(theme.palette.common.black, 0.1)}`,
                  },
                },
              }}
            >
              <MenuItem
                onClick={() => {
                  handleClose();
                  navigate("/settings/profile");
                }}
              >
                {t("common.profile")}
              </MenuItem>
              <MenuItem onClick={handleLogout} sx={{ color: "error.main" }}>
                {t("common.logout")}
              </MenuItem>
            </Menu>
          </Box>
          <Box sx={{ px: isCollapsed ? 1 : 2, pb: 2 }}>
            <ThemeToggle isCollapsed={isCollapsed} />
          </Box>
        </Box>
      </Box>
    </Drawer>
  );
}

export default Sidebar;
