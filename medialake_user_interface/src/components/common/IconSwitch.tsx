import React from "react";
import { Switch, SwitchProps } from "@mui/material";
import { styled } from "@mui/material/styles";
import { colorTokens } from "@/theme/tokens";

export interface IconSwitchProps extends SwitchProps {
  onIcon?: React.ReactNode | string;
  offIcon?: React.ReactNode | string;
  onColor?: string;
  offColor?: string;
  trackOnColor?: string;
  trackOffColor?: string;
}

/**
 * IconSwitch component - A styled switch with customizable icons and colors
 *
 * Uses theme.palette.primary and theme.palette.accent instead of direct
 * colorTokens imports so it responds correctly to theme changes.
 */
const IconSwitch = styled(Switch)<IconSwitchProps>(({
  theme,
  onIcon,
  offIcon,
  onColor,
  offColor,
  trackOnColor,
  trackOffColor,
}) => {
  // Access accent from the custom palette (falls back to primary if missing)
  const accent = (theme.palette as any).accent ?? theme.palette.primary;

  return {
    width: 62,
    height: 34,
    padding: 7,
    "& .MuiSwitch-switchBase": {
      margin: 1,
      padding: 0,
      transform: "translateX(6px)",
      "&.Mui-checked": {
        color: theme.palette.common.white,
        transform: "translateX(22px)",
        "& .MuiSwitch-thumb:before": {
          backgroundImage:
            typeof onIcon === "string"
              ? `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                  theme.palette.common.white
                )}">${onIcon}</svg>')`
              : `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                  theme.palette.common.white
                )}"><path d="M0 0h24v24H0z" fill="none"/><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z"/></svg>')`,
        },
        "& + .MuiSwitch-track": {
          opacity: 1,
          backgroundColor: trackOnColor || accent.light,
          ...theme.applyStyles("dark", {
            backgroundColor: trackOnColor || accent.dark,
          }),
        },
      },
    },
    "& .MuiSwitch-thumb": {
      backgroundColor: offColor || theme.palette.primary.dark,
      width: 32,
      height: 32,
      borderRadius: "25%",
      "&::before": {
        content: "''",
        position: "absolute" as const,
        width: "100%",
        height: "100%",
        left: 0,
        top: 0,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "center",
        backgroundSize: "20px",
        backgroundImage:
          typeof offIcon === "string"
            ? `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                theme.palette.common.white
              )}">${offIcon}</svg>')`
            : `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                theme.palette.common.white
              )}"><path d="M0 0h24v24H0z" fill="none"/><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z"/></svg>')`,
      },
      ...theme.applyStyles("dark", {
        backgroundColor: offColor || theme.palette.primary.main,
      }),
    },
    "& .MuiSwitch-switchBase.Mui-checked .MuiSwitch-thumb": {
      backgroundColor: onColor || theme.palette.primary.dark,
      width: 32,
      height: 32,
      borderRadius: "25%",
      ...theme.applyStyles("dark", {
        backgroundColor: onColor || theme.palette.primary.main,
      }),
    },
    "& .MuiSwitch-track": {
      opacity: 1,
      backgroundColor: trackOffColor || theme.palette.text.secondary,
      borderRadius: 20 / 2,
      ...theme.applyStyles("dark", {
        backgroundColor: trackOffColor || theme.palette.text.secondary,
      }),
    },
  };
});

export default IconSwitch;
