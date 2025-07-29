import React from "react";
import {
  Button as MuiButton,
  ButtonProps as MuiButtonProps,
  styled,
} from "@mui/material";

export interface ButtonProps extends Omit<MuiButtonProps, "size"> {
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const StyledButton = styled(MuiButton)(({ theme }) => ({
  height: "40px", // Consistent height
  minWidth: "80px", // Minimum width
  padding: "0 16px",
  textTransform: "none",
  fontWeight: 500,
  fontSize: "14px",
  lineHeight: "20px",
  borderRadius: "4px",
  "&.MuiButton-contained": {
    backgroundColor: theme.palette.primary.main,
    color: "#fff",
    "&:hover": {
      backgroundColor: theme.palette.primary.dark,
    },
  },
  "&.MuiButton-outlined": {
    borderColor: theme.palette.primary.main,
    color: theme.palette.primary.main,
    "&:hover": {
      backgroundColor: theme.palette.primary.main + "0A", // 4% opacity
    },
  },
  "&.MuiButton-text": {
    color: theme.palette.primary.main,
    "&:hover": {
      backgroundColor: theme.palette.primary.main + "0A", // 4% opacity
    },
  },
  "& .MuiButton-startIcon": {
    marginRight: "8px",
  },
  "& .MuiButton-endIcon": {
    marginLeft: "8px",
  },
}));

export const Button: React.FC<ButtonProps> = ({ children, ...props }) => {
  return <StyledButton {...props}>{children}</StyledButton>;
};

export default Button;
