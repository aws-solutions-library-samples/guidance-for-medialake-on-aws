import React from "react";
import { Switch, SwitchProps } from "@mui/material";
import { styled } from "@mui/material/styles";

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
 * This component extends the MUI Switch with custom styling and icons
 * that appear in the thumb of the switch for both on and off states.
 *
 * @param onIcon - React component or SVG path for the icon when switch is on
 * @param offIcon - React component or SVG path for the icon when switch is off
 * @param onColor - Background color of the thumb when switch is on
 * @param offColor - Background color of the thumb when switch is off
 * @param trackOnColor - Background color of the track when switch is on
 * @param trackOffColor - Background color of the track when switch is off
 */
const IconSwitch = styled(Switch)<IconSwitchProps>(
  ({
    theme,
    onIcon,
    offIcon,
    onColor,
    offColor,
    trackOnColor,
    trackOffColor,
  }) => ({
    width: 62,
    height: 34,
    padding: 7,
    "& .MuiSwitch-switchBase": {
      margin: 1,
      padding: 0,
      transform: "translateX(6px)",
      "&.Mui-checked": {
        color: "#fff",
        transform: "translateX(22px)",
        "& .MuiSwitch-thumb:before": {
          backgroundImage:
            typeof onIcon === "string"
              ? `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                  "#fff",
                )}">${onIcon}</svg>')`
              : `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                  "#fff",
                )}"><path d="M0 0h24v24H0z" fill="none"/><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z"/></svg>')`,
        },
        "& + .MuiSwitch-track": {
          opacity: 1,
          backgroundColor: trackOnColor || "#aab4be",
          ...theme.applyStyles("dark", {
            backgroundColor: trackOnColor || "#8796A5",
          }),
        },
      },
    },
    "& .MuiSwitch-thumb": {
      backgroundColor: offColor || "#001e3c",
      width: 32,
      height: 32,
      borderRadius: "25%",
      "&::before": {
        content: "''",
        position: "absolute",
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
                "#fff",
              )}">${offIcon}</svg>')`
            : `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" height="20px" viewBox="0 0 24 24" width="20px" fill="${encodeURIComponent(
                "#fff",
              )}"><path d="M0 0h24v24H0z" fill="none"/><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z"/></svg>')`,
      },
      ...theme.applyStyles("dark", {
        backgroundColor: offColor || "#003892",
      }),
    },
    "& .MuiSwitch-switchBase.Mui-checked .MuiSwitch-thumb": {
      backgroundColor: onColor || "#001e3c",
      width: 32,
      height: 32,
      borderRadius: "25%",
      ...theme.applyStyles("dark", {
        backgroundColor: onColor || "#003892",
      }),
    },
    "& .MuiSwitch-track": {
      opacity: 1,
      backgroundColor: trackOffColor || "#aab4be",
      borderRadius: 20 / 2,
      ...theme.applyStyles("dark", {
        backgroundColor: trackOffColor || "#8796A5",
      }),
    },
  }),
);

export default IconSwitch;
