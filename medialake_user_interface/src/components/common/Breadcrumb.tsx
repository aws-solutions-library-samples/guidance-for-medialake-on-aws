import React from "react";
import { Box, Typography, IconButton } from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import HistoryIcon from "@mui/icons-material/History";
import { Link } from "react-router-dom";

interface BreadcrumbProps {
  searchQuery?: string;
  currentResult?: string;
  totalResults?: number;
  onBack?: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
}

const Breadcrumb: React.FC<BreadcrumbProps> = ({
  searchQuery,
  currentResult,
  totalResults,
  onBack,
  onPrevious,
  onNext,
}) => {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        p: 2,
        bgcolor: "background.paper",
        borderBottom: 1,
        borderColor: "divider",
        position: "sticky",
        top: 0,
        zIndex: 1100,
      }}
    >
      <Link
        to="/search"
        style={{
          textDecoration: "none",
          color: "inherit",
          display: "flex",
          alignItems: "center",
        }}
      >
        <ArrowBackIcon sx={{ mr: 1 }} />
        <Typography variant="body1" color="primary">
          Back to search
        </Typography>
      </Link>

      <NavigateNextIcon sx={{ color: "text.secondary" }} />

      <Typography variant="body1" color="text.secondary">
        Search: "{searchQuery}"
      </Typography>

      <NavigateNextIcon sx={{ color: "text.secondary" }} />

      <Typography variant="body1" color="text.secondary">
        Result {currentResult} of {totalResults}
      </Typography>

      <Box sx={{ ml: "auto", display: "flex", gap: 1 }}>
        <IconButton onClick={onPrevious} size="small">
          <ArrowBackIcon />
        </IconButton>
        <IconButton onClick={onNext} size="small">
          <NavigateNextIcon />
        </IconButton>
        <IconButton size="small">
          <HistoryIcon />
        </IconButton>
      </Box>
    </Box>
  );
};

export default Breadcrumb;
