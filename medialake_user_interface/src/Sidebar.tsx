import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { signOut, fetchUserAttributes } from "aws-amplify/auth";
import { useAuth } from "./common/hooks/auth-context";
import { useDirection } from "./contexts/DirectionContext";
import { Can, usePermission } from "./permissions";
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
  Security as SecurityIcon,
  Home as HomeIcon,
  Extension as IntegrationIcon,
  Cloud as EnvironmentIcon,
  Terrain as LogoIcon,
} from "@mui/icons-material";
import { useLocation, useNavigate } from "react-router-dom";
import { useTheme as useCustomTheme } from "./hooks/useTheme";
import { useSidebar } from "./contexts/SidebarContext";
import { ThemeToggle } from "./components/ThemeToggle";

import { drawerWidth, collapsedDrawerWidth } from "@/constants";

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
          t(
            "app.errors.loadingUserAttributes",
            "Error loading user attributes:",
          ),
          error,
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
    return customTheme === "dark" ? "white" : theme.palette.text.secondary;
  };

  const { ability, loading: permissionsLoading } = usePermission();

  // Feature flags
  const advancedPermissionsEnabled = useFeatureFlag(
    "advanced-permissions-enabled",
    false,
  );

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
        console.error(
          `Error checking ${action} permission on ${resource}:`,
          error,
        );
        // During errors, default to false but log the error
        return false;
      }
    },
    [ability],
  );

  // Memoize permission checks with error handling
  const canViewSettings = useMemo(() => {
    try {
      // Check if user has any settings-related permissions
      return (
        (ability?.can("view", "settings") ||
          ability?.can("view", "user") ||
          ability?.can("view", "group") ||
          ability?.can("view", "permission-set") ||
          ability?.can("view", "connector") ||
          ability?.can("view", "integration") ||
          safePermissionCheck("view", "settings.users") ||
          safePermissionCheck("view", "settings.connectors") ||
          safePermissionCheck("view", "settings.integrations") ||
          safePermissionCheck("view", "settings.system") ||
          safePermissionCheck("view", "settings.permissions")) ??
        false
      );
    } catch (error) {
      console.error("Error checking settings permission:", error);
      return false;
    }
  }, [ability, safePermissionCheck]);

  // Build menu items based on permissions
  const mainMenuItems = [
    {
      text: t("sidebar.menu.home"),
      icon: <HomeIcon />,
      path: "/",
      visible: true, // Always show home
    },
    {
      text: t("sidebar.menu.assets"),
      icon: <MediaAssetsIcon />,
      path: "/assets",
      visible: true, // Assets should always be shown
    },
    {
      text: t("sidebar.menu.pipelines"),
      icon: <PipelineIcon />,
      path: "/pipelines",
      visible: canViewPipeline,
    },
    {
      text: t("sidebar.menu.pipelineExecutions"),
      icon: <ExecutionsIcon />,
      path: "/executions",
      visible: canViewPipeline,
    },
    {
      text: t("sidebar.menu.settings"),
      icon: <SettingsIcon />,
      onClick: () => setSettingsOpen(!settingsOpen),
      isExpandable: true,
      isExpanded: settingsOpen,
      visible: canViewSettings,
      subItems: [
        {
          text: t("sidebar.submenu.connectors"),
          icon: <StorageIcon />,
          path: "/settings/connectors",
          visible:
            safePermissionCheck("view", "connector") ||
            safePermissionCheck("view", "settings.connectors"),
        },
        {
          text: t("sidebar.submenu.usersAndGroups", "Users and Groups"),
          icon: <GroupIcon />,
          path: "/settings/users-groups",
          visible:
            safePermissionCheck("view", "user") ||
            safePermissionCheck("view", "group") ||
            safePermissionCheck("view", "settings.users"),
        },
        {
          text: t("sidebar.submenu.permissionSets", "Permissions"),
          icon: <SecurityIcon />,
          path: "/settings/permission-sets",
          visible:
            advancedPermissionsEnabled &&
            safePermissionCheck("view", "permission-set"),
        },
        {
          text: t("sidebar.submenu.integrations"),
          icon: <IntegrationIcon />,
          path: "/settings/integrations",
          visible:
            safePermissionCheck("view", "integration") ||
            safePermissionCheck("view", "settings.integrations"),
        },
        // { text: t('sidebar.submenu.environments'), icon: <EnvironmentIcon />, path: '/settings/environments' },
        {
          text: t("sidebar.submenu.system"),
          icon: <SettingsIcon />,
          path: "/settings/system",
          visible:
            safePermissionCheck("view", "settings") ||
            safePermissionCheck("view", "settings.system"),
        },
      ].filter((item) => item.visible !== false),
    },
  ].filter((item) => item.visible !== false);

  const handleNavigation = (path: string) => {
    // Don't navigate if:
    // 1. We're already on this exact path, or
    // 2. We're on a sub-route of this path (except for root path '/')
    if (
      location.pathname === path ||
      (path !== "/" && location.pathname.startsWith(path))
    ) {
      console.log(
        `${t("app.navigation.preventedDuplicate", "Prevented duplicate navigation to")} ${path}`,
      );
      return;
    }

    // Log navigation for debugging
    console.log(
      `${t("app.navigation.navigating", "Navigating from")} ${location.pathname} to ${path}`,
    );
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
        transition: (theme) =>
          theme.transitions.create(["width"], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        "& .MuiDrawer-paper": {
          width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
          boxSizing: "border-box",
          borderRight: isRTL ? "none" : "1px solid rgba(0,0,0,0.08)",
          borderLeft: isRTL ? "1px solid rgba(0,0,0,0.08)" : "none",
          backgroundColor: theme.palette.background.paper,
          position: "fixed",
          height: "100vh",
          top: 0,
          [isRTL ? "right" : "left"]: 0,
          overflow: "visible",
          transition: (theme) =>
            theme.transitions.create(["width"], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
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
            boxShadow: "0px 2px 4px rgba(0, 0, 0, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "1px solid",
            borderColor: "divider",
            zIndex: 9999,
            padding: 0,
            "&:hover": {
              bgcolor: "background.paper",
              boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
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
            // If this is the Settings menu item, wrap it with Can component
            if (item.text === t("sidebar.menu.settings")) {
              return (
                <Can key={item.text} I="view" a="settings">
                  <React.Fragment>
                    <ListItem disablePadding>
                      {isCollapsed ? (
                        <Tooltip title={item.text} placement="right">
                          <ListItemButton
                            onClick={
                              item.isExpandable
                                ? item.onClick
                                : () => handleNavigation(item.path || "/")
                            }
                            sx={{
                              minHeight: 48,
                              justifyContent: "center",
                              px: 2.5,
                              backgroundColor:
                                isActive(item.path || "") ||
                                (item.isExpandable && item.isExpanded)
                                  ? `${theme.palette.primary.main}08`
                                  : "transparent",
                              "&:hover": {
                                backgroundColor: `${theme.palette.primary.main}15`,
                              },
                            }}
                          >
                            <ListItemIcon
                              sx={{
                                minWidth: 0,
                                mr: "auto",
                                justifyContent: "center",
                                color: getIconColor(
                                  isActive(item.path || "") ||
                                    (item.isExpandable && item.isExpanded),
                                ),
                              }}
                            >
                              {item.icon}
                            </ListItemIcon>
                          </ListItemButton>
                        </Tooltip>
                      ) : (
                        <ListItemButton
                          onClick={
                            item.isExpandable
                              ? item.onClick
                              : () => handleNavigation(item.path || "/")
                          }
                          sx={{
                            backgroundColor:
                              isActive(item.path || "") ||
                              (item.isExpandable && item.isExpanded)
                                ? `${theme.palette.primary.main}08`
                                : "transparent",
                            "&:hover": {
                              backgroundColor: `${theme.palette.primary.main}15`,
                            },
                            borderRight:
                              isActive(item.path || "") && !isRTL
                                ? `3px solid ${theme.palette.primary.main}`
                                : "none",
                            borderLeft:
                              isActive(item.path || "") && isRTL
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
                                isActive(item.path || "") ||
                                  (item.isExpandable && item.isExpanded),
                              ),
                              minWidth: "40px",
                            }}
                          >
                            {item.icon}
                          </ListItemIcon>
                          <ListItemText
                            primary={
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight:
                                    isActive(item.path || "") ||
                                    (item.isExpandable && item.isExpanded)
                                      ? 600
                                      : 400,
                                  color:
                                    isActive(item.path || "") ||
                                    (item.isExpandable && item.isExpanded)
                                      ? theme.palette.primary.main
                                      : customTheme === "dark"
                                        ? "white"
                                        : theme.palette.text.primary,
                                  textAlign: isRTL ? "right" : "left",
                                }}
                              >
                                {item.text}
                              </Typography>
                            }
                            sx={{ textAlign: isRTL ? "right" : "left" }}
                          />
                          {item.isExpandable && (
                            <Box
                              sx={{
                                color:
                                  customTheme === "dark" ? "white" : "inherit",
                              }}
                            >
                              {item.isExpanded ? (
                                <ExpandLess />
                              ) : (
                                <ExpandMore />
                              )}
                            </Box>
                          )}
                        </ListItemButton>
                      )}
                    </ListItem>
                    {!isCollapsed && item.isExpandable && item.subItems && (
                      <Collapse
                        in={item.isExpanded}
                        timeout="auto"
                        unmountOnExit
                      >
                        <List component="div" disablePadding>
                          {item.subItems.map((subItem) => (
                            <ListItem key={subItem.text} disablePadding>
                              <ListItemButton
                                onClick={() => handleNavigation(subItem.path)}
                                sx={{
                                  [isRTL ? "pr" : "pl"]: 6,
                                  backgroundColor: isSettingsActive(
                                    subItem.path,
                                  )
                                    ? `${theme.palette.primary.main}08`
                                    : "transparent",
                                  "&:hover": {
                                    backgroundColor: `${theme.palette.primary.main}15`,
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
                                  justifyContent: isRTL
                                    ? "flex-start"
                                    : "flex-start",
                                }}
                              >
                                <ListItemIcon
                                  sx={{
                                    color: getIconColor(
                                      isSettingsActive(subItem.path),
                                    ),
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
                                        fontWeight: isSettingsActive(
                                          subItem.path,
                                        )
                                          ? 600
                                          : 400,
                                        color: isSettingsActive(subItem.path)
                                          ? theme.palette.primary.main
                                          : customTheme === "dark"
                                            ? "white"
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
                          ))}
                        </List>
                      </Collapse>
                    )}
                  </React.Fragment>
                </Can>
              );
            }

            // For other menu items, render normally
            return (
              <React.Fragment key={item.text}>
                <ListItem disablePadding>
                  {isCollapsed ? (
                    <Tooltip title={item.text} placement="right">
                      <ListItemButton
                        onClick={
                          item.isExpandable
                            ? item.onClick
                            : () => handleNavigation(item.path || "/")
                        }
                        sx={{
                          minHeight: 48,
                          justifyContent: "center",
                          px: 2.5,
                          backgroundColor:
                            isActive(item.path || "") ||
                            (item.isExpandable && item.isExpanded)
                              ? `${theme.palette.primary.main}08`
                              : "transparent",
                          "&:hover": {
                            backgroundColor: `${theme.palette.primary.main}15`,
                          },
                        }}
                      >
                        <ListItemIcon
                          sx={{
                            minWidth: 0,
                            mr: "auto",
                            justifyContent: "center",
                            color: getIconColor(
                              isActive(item.path || "") ||
                                (item.isExpandable && item.isExpanded),
                            ),
                          }}
                        >
                          {item.icon}
                        </ListItemIcon>
                      </ListItemButton>
                    </Tooltip>
                  ) : (
                    <ListItemButton
                      onClick={
                        item.isExpandable
                          ? item.onClick
                          : () => handleNavigation(item.path || "/")
                      }
                      sx={{
                        backgroundColor:
                          isActive(item.path || "") ||
                          (item.isExpandable && item.isExpanded)
                            ? `${theme.palette.primary.main}08`
                            : "transparent",
                        "&:hover": {
                          backgroundColor: `${theme.palette.primary.main}15`,
                        },
                        borderRight:
                          isActive(item.path || "") && !isRTL
                            ? `3px solid ${theme.palette.primary.main}`
                            : "none",
                        borderLeft:
                          isActive(item.path || "") && isRTL
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
                            isActive(item.path || "") ||
                              (item.isExpandable && item.isExpanded),
                          ),
                          minWidth: "40px",
                        }}
                      >
                        {item.icon}
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight:
                                isActive(item.path || "") ||
                                (item.isExpandable && item.isExpanded)
                                  ? 600
                                  : 400,
                              color:
                                isActive(item.path || "") ||
                                (item.isExpandable && item.isExpanded)
                                  ? theme.palette.primary.main
                                  : customTheme === "dark"
                                    ? "white"
                                    : theme.palette.text.primary,
                              textAlign: isRTL ? "right" : "left",
                            }}
                          >
                            {item.text}
                          </Typography>
                        }
                        sx={{ textAlign: isRTL ? "right" : "left" }}
                      />
                      {item.isExpandable && (
                        <Box
                          sx={{
                            color: customTheme === "dark" ? "white" : "inherit",
                          }}
                        >
                          {item.isExpanded ? <ExpandLess /> : <ExpandMore />}
                        </Box>
                      )}
                    </ListItemButton>
                  )}
                </ListItem>
                {!isCollapsed && item.isExpandable && item.subItems && (
                  <Collapse in={item.isExpanded} timeout="auto" unmountOnExit>
                    <List component="div" disablePadding>
                      {item.subItems.map((subItem) => {
                        // Check if this is a system settings item that requires permission
                        const isSystemSettings =
                          subItem.path === "/settings/system" ||
                          subItem.path === "/settings/users-groups" ||
                          subItem.path === "/settings/permission-sets";

                        // Wrap system settings items with Can component
                        const menuItem = (
                          <ListItem key={subItem.text} disablePadding>
                            <ListItemButton
                              onClick={() => handleNavigation(subItem.path)}
                              sx={{
                                [isRTL ? "pr" : "pl"]: 6,
                                backgroundColor: isSettingsActive(subItem.path)
                                  ? `${theme.palette.primary.main}08`
                                  : "transparent",
                                "&:hover": {
                                  backgroundColor: `${theme.palette.primary.main}15`,
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
                                justifyContent: isRTL
                                  ? "flex-start"
                                  : "flex-start",
                              }}
                            >
                              <ListItemIcon
                                sx={{
                                  color: getIconColor(
                                    isSettingsActive(subItem.path),
                                  ),
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
                                      fontWeight: isSettingsActive(subItem.path)
                                        ? 600
                                        : 400,
                                      color: isSettingsActive(subItem.path)
                                        ? theme.palette.primary.main
                                        : customTheme === "dark"
                                          ? "white"
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

                        // Return the menu item wrapped in Can component if it's a system settings item
                        return isSystemSettings ? (
                          <Can key={subItem.text} I="view" a="settings">
                            {menuItem}
                          </Can>
                        ) : (
                          menuItem
                        );
                      })}
                    </List>
                  </Collapse>
                )}
              </React.Fragment>
            );
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
              <Tooltip
                title={userName || t("common.profile")}
                placement="right"
              >
                <IconButton
                  onClick={handleProfileClick}
                  sx={{
                    width: "100%",
                    height: 40,
                    borderRadius: "8px",
                    "&:hover": {
                      backgroundColor: `${theme.palette.primary.main}15`,
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
                    backgroundColor: `${theme.palette.primary.main}15`,
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
                    color:
                      customTheme === "dark"
                        ? "white"
                        : theme.palette.text.primary,
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
                    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
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
