import React, { Suspense } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { RouterProvider } from "react-router/dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { SnackbarProvider } from "notistack";
import queryClient from "../api/queryClient";
import { AwsConfigProvider } from "../common/hooks/aws-config-context";
import { AuthProvider } from "../common/hooks/auth-context";
import { PermissionProvider } from "../permissions";
import "@aws-amplify/ui-react/styles.css";
import { ModalProvider } from "./common/ModalConnector";
import { ThemeProvider } from "../hooks/useTheme";
import { ThemeWrapper } from "./ThemeWrapper";
import { TimezoneProvider } from "../contexts/TimezoneContext";
import { TableDensityProvider } from "../contexts/TableDensityContext";
import { DirectionProvider } from "../contexts/DirectionContext";
import { router } from "../routes/router";
import { Box, CircularProgress } from "@mui/material";
import { NotificationProvider } from "./NotificationCenter";
import { JobNotificationSync } from "./JobNotificationSync";
import { TokenRefreshManager } from "./TokenRefreshManager";
import { useTranslation } from "react-i18next";

const LoadingFallback = () => (
  <Box
    sx={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "100vh",
    }}
  >
    <CircularProgress />
  </Box>
);

const ErrorFallback = ({ error }: { error: unknown }) => {
  const { t } = useTranslation();
  const message = error instanceof Error ? error.message : String(error);
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <h2>{t("app.errors.somethingWentWrong")}:</h2>
      <pre style={{ color: "red" }}>{message}</pre>
    </Box>
  );
};

const AppConfigured = () => {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <Suspense fallback={<LoadingFallback />}>
        <QueryClientProvider client={queryClient}>
          <AwsConfigProvider>
            <AuthProvider>
              <TokenRefreshManager>
                <PermissionProvider>
                  <TimezoneProvider>
                    <ThemeProvider>
                      <DirectionProvider>
                        <TableDensityProvider>
                          <ThemeWrapper>
                            {/*
                              BUG-12 / BUG-20: notistack's ``useSnackbar`` is
                              a no-op unless the tree is wrapped in a
                              ``SnackbarProvider``. Without one, retry buttons,
                              bulk-download start, favorite add/remove and
                              every other place that calls ``enqueueSnackbar``
                              silently swallowed their user feedback. Placed
                              inside the theme wrapper so notistack picks up
                              the current MUI theme; kept outside routing so a
                              toast enqueued during a route transition still
                              renders. Also bumps the max stack to 3 so a
                              rapid-fire action (e.g. selecting multiple
                              assets then triggering bulk download) doesn't
                              hide the earlier notice.
                            */}
                            <SnackbarProvider
                              maxSnack={3}
                              autoHideDuration={4000}
                              anchorOrigin={{
                                vertical: "bottom",
                                horizontal: "right",
                              }}
                            >
                              <ModalProvider>
                                <NotificationProvider>
                                  <JobNotificationSync />
                                  <RouterProvider router={router} />
                                </NotificationProvider>
                              </ModalProvider>
                            </SnackbarProvider>
                          </ThemeWrapper>
                        </TableDensityProvider>
                      </DirectionProvider>
                    </ThemeProvider>
                  </TimezoneProvider>
                </PermissionProvider>
              </TokenRefreshManager>
            </AuthProvider>
          </AwsConfigProvider>
        </QueryClientProvider>
      </Suspense>
    </ErrorBoundary>
  );
};

export default AppConfigured;
