import { useState } from "react";
import { useSnackbar as useNotistack } from "notistack";

type SnackbarSeverity = "success" | "error" | "warning" | "info";

interface SnackbarOptions {
  message: string;
  severity?: SnackbarSeverity;
  autoHideDuration?: number;
  action?: React.ReactNode;
}

export const useSnackbar = () => {
  const { enqueueSnackbar, closeSnackbar } = useNotistack();

  const showSnackbar = ({
    message,
    severity = "info",
    autoHideDuration = 3000,
    action,
  }: SnackbarOptions) => {
    enqueueSnackbar(message, {
      variant: severity,
      autoHideDuration,
      action,
    });
  };

  return { showSnackbar, closeSnackbar };
};
