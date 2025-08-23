import React from "react";
import { Box, Typography, Paper } from "@mui/material";
import SearchOffIcon from "@mui/icons-material/SearchOff";

interface NoResultsFoundProps {
  query: string;
}

const NoResultsFound: React.FC<NoResultsFoundProps> = ({ query }) => {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "50vh",
        textAlign: "center",
        gap: 2,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 4,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 2,
          bgcolor: "background.paper",
          borderRadius: 2,
        }}
      >
        <SearchOffIcon
          sx={{
            fontSize: 64,
            color: "text.secondary",
            mb: 2,
          }}
        />
        <Typography variant="h5" color="text.primary" gutterBottom>
          No results found
        </Typography>
        <Typography variant="body1" color="text.secondary">
          We couldn't find any matches for "{query}"
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Try adjusting your search or filters to find what you're looking for
        </Typography>
      </Paper>
    </Box>
  );
};

export default NoResultsFound;
