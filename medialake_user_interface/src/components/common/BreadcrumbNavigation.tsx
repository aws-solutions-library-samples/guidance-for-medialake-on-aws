import React, { useState } from "react";
import {
  Box,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  Divider,
} from "@mui/material";
import { ChevronLeft, ChevronRight, History, Trash2 } from "lucide-react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useRecentlyViewed } from "../../contexts/RecentlyViewedContext";
import { formatDistanceToNow } from "date-fns";

interface BreadcrumbNavigationProps {
  searchTerm: string;
  currentResult: number;
  totalResults: number;
  onBack: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
  assetName?: string;
  assetId?: string;
  assetType?: string;
}

const BreadcrumbNavigation: React.FC<BreadcrumbNavigationProps> = ({
  searchTerm,
  currentResult,
  totalResults,
  onBack,
  onPrevious,
  onNext,
  assetName,
  assetId,
  assetType,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const { items, clearAll } = useRecentlyViewed();
  const navigate = useNavigate();
  const location = useLocation();

  const handleHistoryClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleHistoryClose = () => {
    setAnchorEl(null);
  };

  const handleBackClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Use browser's history API to go back
    window.history.back();
  };

  // Only show breadcrumb navigation on detail pages
  if (!assetName || !assetId || !assetType) {
    return null;
  }

  return (
    <Box
      sx={{
        position: "sticky",
        top: 64,
        zIndex: 1100,
        bgcolor: "transparent",
        px: 0,
        py: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      {/* Left Section */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <IconButton onClick={handleBackClick} size="small">
          <ChevronLeft />
        </IconButton>
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <Box
            onClick={handleBackClick}
            sx={{
              cursor: "pointer",
              "&:hover": { textDecoration: "underline" },
            }}
          >
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Search{searchTerm ? `: "${searchTerm}"` : ""}
            </Typography>
          </Box>
          <Typography variant="body2" sx={{ color: "text.secondary", mx: 1 }}>
            /
          </Typography>
          <Typography variant="body2">{assetName}</Typography>
        </Box>
      </Box>

      {/* Right Section - Only History */}
      <Box sx={{ display: "flex", alignItems: "center" }}>
        <IconButton
          onClick={handleHistoryClick}
          size="small"
          aria-label="show history"
        >
          <History />
        </IconButton>
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleHistoryClose}
          anchorOrigin={{
            vertical: "bottom",
            horizontal: "right",
          }}
          transformOrigin={{
            vertical: "top",
            horizontal: "right",
          }}
          PaperProps={{
            sx: { minWidth: 280 },
          }}
        >
          <Box
            sx={{
              px: 2,
              py: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>
              Recently Viewed
            </Typography>
            <IconButton
              size="small"
              onClick={clearAll}
              sx={{ color: "text.secondary" }}
            >
              <Trash2 size={16} />
            </IconButton>
          </Box>
          <Divider />
          {items.length === 0 ? (
            <Box sx={{ p: 2 }}>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                No recently viewed items
              </Typography>
            </Box>
          ) : (
            items.map((item) => (
              <MenuItem
                key={item.id}
                onClick={() => {
                  handleHistoryClose();
                  navigate(
                    `${item.path}${
                      item.searchTerm
                        ? `?searchTerm=${encodeURIComponent(item.searchTerm)}`
                        : ""
                    }`,
                  );
                }}
                sx={{
                  py: 1,
                  px: 2,
                }}
              >
                <Box sx={{ width: "100%" }}>
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      mb: 0.5,
                    }}
                  >
                    <Typography
                      sx={{
                        fontSize: "0.875rem",
                        fontWeight: 500,
                        maxWidth: "80%",
                      }}
                    >
                      {item.title}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ color: "text.secondary" }}
                    >
                      {formatDistanceToNow(item.timestamp, { addSuffix: true })}
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      display: "flex",
                      gap: 2,
                      alignItems: "center",
                    }}
                  >
                    {item.metadata.duration && (
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        {item.metadata.duration}
                      </Typography>
                    )}
                    {item.metadata.dimensions && (
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        {item.metadata.dimensions}
                      </Typography>
                    )}
                    {item.metadata.fileSize && (
                      <Typography
                        variant="caption"
                        sx={{ color: "text.secondary" }}
                      >
                        {item.metadata.fileSize}
                      </Typography>
                    )}
                  </Box>
                </Box>
              </MenuItem>
            ))
          )}
        </Menu>
      </Box>
    </Box>
  );
};

export default BreadcrumbNavigation;
