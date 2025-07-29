import React from "react";
import { Box, CircularProgress, Alert } from "@mui/material";
import { useDirection } from "../../../contexts/DirectionContext";

interface PageContentProps {
  isLoading?: boolean;
  error?: Error | null;
  children: React.ReactNode;
}

const LoadingState = () => (
  <Box
    sx={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      height: "100%",
      minHeight: 200,
    }}
  >
    <CircularProgress />
  </Box>
);

const ErrorState = ({ error }: { error: Error }) => {
  const { direction } = useDirection();
  const isRTL = direction === "rtl";

  return (
    <Box sx={{ p: 2, textAlign: isRTL ? "right" : "left" }}>
      <Alert
        severity="error"
        sx={{ mb: 2, textAlign: isRTL ? "right" : "left" }}
      >
        {error.message}
      </Alert>
    </Box>
  );
};

const PageContent: React.FC<PageContentProps> = ({
  isLoading = false,
  error = null,
  children,
}) => {
  const { direction } = useDirection();
  const isRTL = direction === "rtl";
  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        minHeight: 0,
        textAlign: isRTL ? "right" : "left",
        direction: isRTL ? "rtl" : "ltr",
      }}
    >
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        children
      )}
    </Box>
  );
};

export default PageContent;
