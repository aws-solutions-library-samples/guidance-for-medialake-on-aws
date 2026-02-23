import React from "react";
import { Box, CircularProgress, Fade } from "@mui/material";

export const LoadingSpinner: React.FC = () => (
  <Fade in timeout={400}>
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
      <CircularProgress size={36} thickness={4} />
    </Box>
  </Fade>
);

export default LoadingSpinner;
